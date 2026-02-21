"""
Reverse Image Search Service.

Uses SerpAPI (google_lens engine) to find where an image appears on the web.
The image is served temporarily from the application's own public URL using a
UUID token stored in Redis — no third-party hosting is involved.

Flow:
  1. Register file_path in Redis under a UUID token (TTL = TOKEN_TTL seconds).
  2. Build the public URL: APP_PUBLIC_URL/plugins/api/temp-image/<token>/<name>
  3. Call SerpAPI google_lens with that URL.
     SerpAPI submits the URL to Google Lens, which downloads the image
     ASYNCHRONOUSLY — potentially AFTER SerpAPI has already returned the
     response to us.  The token therefore must remain valid for at least
     TOKEN_TTL seconds so Google can fetch the image.
  4. The Redis key expires automatically; no manual revocation.

Requirements:
  - APP_PUBLIC_URL env var must be set to the application's publicly reachable
    base URL (e.g. https://investigation.example.com).
  - The URL must not point to localhost / 127.0.0.1.
"""
import os
import uuid
import logging

logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff', '.tif'}

# Keep the token alive long enough for Google's async image fetcher to
# download the file after SerpAPI has already returned its response.
TOKEN_TTL = 600  # 10 minutes


def _is_local(url: str) -> bool:
    """Return True when *url* resolves to a local / non-public host."""
    from urllib.parse import urlparse
    host = (urlparse(url).hostname or '').lower()
    return host in ('localhost', '127.0.0.1', '0.0.0.0', '::1') or host.endswith('.local')


class ReverseImageSearchService:
    """Service for reverse image search via SerpAPI (google_lens engine)."""

    def __init__(self, api_key_model):
        self.api_key = api_key_model.get_api_key()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def search(self, file_path: str) -> dict:
        """
        Perform a reverse image search on a local image file.

        Args:
            file_path: Absolute path to the (decrypted) image file.

        Returns:
            dict with keys: success, image_url, image_results,
            text_results, knowledge_graph, error (on failure).
        """
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in SUPPORTED_FORMATS:
            return {
                'success': False,
                'error': f'Formato no compatible: {ext}. '
                         f'Formatos soportados: {", ".join(sorted(SUPPORTED_FORMATS))}'
            }

        if not os.path.exists(file_path):
            return {'success': False, 'error': 'Archivo no encontrado'}

        # Step 1 — register in Redis and get public URL
        try:
            image_url = self._create_token_url(file_path)
        except Exception as exc:
            logger.error(f"Reverse image search: token creation failed: {exc}")
            return {'success': False, 'error': str(exc)}

        # Step 2 — SerpAPI google_lens
        # Note: do NOT revoke the token here — Google fetches asynchronously
        # and may try to download the image after SerpAPI returns.
        # The Redis TTL (TOKEN_TTL seconds) handles automatic cleanup.
        try:
            raw = self._call_serpapi(image_url)
        except Exception as exc:
            logger.error(f"Reverse image search: SerpAPI failed: {exc}")
            return {'success': False, 'error': f'Error en SerpAPI: {exc}'}

        return self._format_results(raw, image_url)

    def test_connection(self) -> dict:
        """Quick check that the SerpAPI key is valid."""
        try:
            from serpapi import GoogleSearch
            result = GoogleSearch({
                'engine': 'google', 'q': 'test',
                'api_key': self.api_key, 'num': 1,
            }).get_dict()
            if 'error' in result:
                return {'success': False, 'error': result['error']}
            return {'success': True, 'message': 'Conexión con SerpAPI correcta'}
        except Exception as exc:
            return {'success': False, 'error': str(exc)}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _create_token_url(self, file_path: str) -> str:
        """
        Register *file_path* in Redis and return the public URL.

        Raises:
            ValueError if APP_PUBLIC_URL is missing or local.
        """
        import redis as redis_lib
        from flask import current_app

        public_url = current_app.config.get('APP_PUBLIC_URL', '').rstrip('/')
        if not public_url:
            raise ValueError(
                'APP_PUBLIC_URL no está configurada. '
                'Añade APP_PUBLIC_URL=https://tu-dominio.com al fichero .env.'
            )
        if _is_local(public_url):
            raise ValueError(
                'APP_PUBLIC_URL apunta a localhost; '
                'se necesita una URL pública accesible desde internet.'
            )

        token = str(uuid.uuid4())
        r = redis_lib.from_url(current_app.config['REDIS_URL'])
        r.setex(f'ris_token:{token}', TOKEN_TTL, file_path)

        filename = os.path.basename(file_path)
        url = f'{public_url}/plugins/api/temp-image/{token}/{filename}'
        logger.info(f"Reverse image search: token registered (TTL {TOKEN_TTL}s) → {url}")
        return url

    def _call_serpapi(self, image_url: str) -> dict:
        """Call SerpAPI google_lens with the image URL."""
        from serpapi import GoogleSearch

        params = {
            'engine': 'google_lens',
            'url': image_url,
            'api_key': self.api_key,
            'hl': 'es',
            'country': 'es',
        }
        data = GoogleSearch(params).get_dict()

        # Real errors (invalid key, quota, …) arrive without search_metadata.
        if 'error' in data and 'search_metadata' not in data:
            raise ValueError(data['error'])

        return data

    def _format_results(self, data: dict, image_url: str) -> dict:
        """Convert raw SerpAPI google_lens response to a structured dict."""

        # Visual matches — pages/products where the image appears
        image_results = []
        for item in data.get('visual_matches', []):
            image_results.append({
                'position': item.get('position'),
                'title': item.get('title', ''),
                'link': item.get('link', ''),
                'source': item.get('source', ''),
                'snippet': item.get('snippet', ''),
                'thumbnail': item.get('thumbnail', ''),
                'price': item.get('price'),
            })

        # Text detected in the image
        text_results = []
        for item in data.get('text_results', []):
            text_results.append({
                'text': item.get('text', ''),
                'link': item.get('link', ''),
            })

        # Knowledge graph (entity identified by Google)
        kg = data.get('knowledge_graph', {})
        knowledge_graph = None
        if kg:
            knowledge_graph = {
                'title': kg.get('title', ''),
                'subtitle': kg.get('subtitle', ''),
                'description': kg.get('description', ''),
                'images': kg.get('images', []),
            }

        # Link to classic reverse image search
        reverse_link = (data.get('reverse_image_search') or {}).get('link', '')

        no_results_msg = data.get('error') if 'error' in data else None

        return {
            'success': True,
            'engine': 'google_lens',
            'image_url': image_url,
            'no_results': no_results_msg is not None,
            'no_results_message': no_results_msg,
            'knowledge_graph': knowledge_graph,
            'image_results': image_results,
            'text_results': text_results,
            'reverse_image_search_link': reverse_link,
            'total_image_results': len(image_results),
            'total_text_results': len(text_results),
        }
