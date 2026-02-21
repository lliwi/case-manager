"""
Reverse Image Search Plugin.

Performs a Google Lens reverse image search on an evidence image using SerpAPI.
The image is served temporarily from the application's own public URL — no
third-party hosting is involved.

Prerequisites:
  - A SerpAPI API key must be active in Admin → API Keys.
  - APP_PUBLIC_URL env var must be set to the application's publicly reachable
    base URL (e.g. https://investigation.example.com).
    If empty or pointing to localhost the plugin reports itself as unavailable.
"""
import logging
import pluggy

from app.services.reverse_image_search_service import _is_local

hookimpl = pluggy.HookimplMarker("casemanager")

logger = logging.getLogger(__name__)


class ReverseImageSearchPlugin:
    """Forensic plugin for reverse image search via SerpAPI (google_lens)."""

    SUPPORTED_FORMATS = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff', '.tif']

    def _get_api_key_model(self):
        try:
            from app.models.api_key import ApiKey
            return ApiKey.query.filter_by(
                service_name='serpapi', is_active=True, is_deleted=False
            ).first()
        except Exception:
            return None

    def _public_url(self) -> str:
        try:
            from flask import current_app
            return current_app.config.get('APP_PUBLIC_URL', '').rstrip('/')
        except Exception:
            return ''

    @hookimpl
    def get_info(self):
        api_key = self._get_api_key_model()
        pub_url = self._public_url()

        if api_key is None:
            unavail = 'No hay API Key de SerpAPI activa configurada en el sistema.'
        elif not pub_url or _is_local(pub_url):
            unavail = (
                'APP_PUBLIC_URL no está configurada o apunta a localhost. '
                'Este plugin requiere que la aplicación sea accesible públicamente desde internet.'
            )
        else:
            unavail = None

        return {
            'name': 'reverse_image_search',
            'display_name': 'Búsqueda Inversa de Imagen (Google Lens)',
            'description': (
                'Realiza una búsqueda inversa con Google Lens mediante SerpAPI: '
                'encuentra dónde aparece la imagen en la web, detecta texto en ella '
                'e identifica el sujeto. La imagen se sirve desde la propia URL '
                'pública de la aplicación sin pasar por servicios de terceros.'
            ),
            'version': '2.1.0',
            'author': 'Case Manager',
            'category': 'forensic',
            'type': 'reverse_image_search',
            'supported_formats': self.SUPPORTED_FORMATS,
            'available': unavail is None,
            'unavailable_reason': unavail,
        }

    @hookimpl
    def analyze_file(self, file_path: str, **kwargs) -> dict:
        info = self.get_info()
        if not info['available']:
            return {'success': False, 'error': info['unavailable_reason']}

        api_key_model = self._get_api_key_model()
        try:
            from app.services.reverse_image_search_service import ReverseImageSearchService
            return ReverseImageSearchService(api_key_model).search(file_path)
        except Exception as exc:
            logger.error(f"ReverseImageSearchPlugin: {exc}")
            return {'success': False, 'error': str(exc)}
