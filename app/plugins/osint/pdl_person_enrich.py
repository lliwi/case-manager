"""
PeopleDataLabs Person Enrichment Plugin.

OSINT plugin for finding social media profiles, employment history,
and contact information from a person's name + company (or email / phone).
Uses the PeopleDataLabs Person Enrichment API v5.
"""
import pluggy
from app.models.api_key import ApiKey
from app.services.pdl_service import PDLService
import logging

hookimpl = pluggy.HookimplMarker("casemanager")
logger = logging.getLogger(__name__)


class PDLPersonEnrichPlugin:
    """
    OSINT plugin for PeopleDataLabs Person Enrichment.

    Features:
    - Social profile discovery (LinkedIn, Twitter/X, Facebook, GitHub, …)
    - Employment and education history
    - Associated emails and phone numbers
    - Location data
    - Match confidence score (likelihood 1-10)
    """

    @hookimpl
    def get_info(self):
        """Get plugin metadata."""
        return {
            'name': 'pdl_person_enrich',
            'display_name': 'PeopleDataLabs - Enriquecimiento de Persona',
            'description': (
                'Obtiene perfiles de redes sociales, historial laboral y datos de contacto '
                'a partir del nombre + empresa, email, teléfono o URL de perfil social, '
                'usando la API de PeopleDataLabs.'
            ),
            'version': '1.0.0',
            'author': 'Case Manager',
            'category': 'osint',
            'type': 'person_enrichment',
            'supported_formats': ['email', 'phone', 'username', 'social_profile', 'other'],
            'requires_api_key': True,
            'api_service': 'peopledatalabs',
        }

    @hookimpl
    def lookup(self, query: str, query_type: str = 'auto', **kwargs) -> dict:
        """
        Perform OSINT person enrichment via PeopleDataLabs.

        Args:
            query: Primary search value (email, phone, username, name, or profile URL)
            query_type: Contact type ('email', 'phone', 'social_profile', 'username', 'other')
            **kwargs:
                name (str): Full person name (used alongside company for disambiguation)
                company (str): Employer name to narrow the search
                location (str): City / region / country to narrow the search

        Returns:
            dict: Enrichment result with social profiles, employment, etc.
        """
        api_key = ApiKey.get_active_key('peopledatalabs')
        if not api_key:
            return {
                'success': False,
                'error': 'No hay API Key activa configurada para PeopleDataLabs',
                'recommendation': (
                    'Configura una API Key de PeopleDataLabs en '
                    'Administración → API Keys'
                ),
            }

        service = PDLService(api_key)

        name = kwargs.get('name', '').strip()
        company = kwargs.get('company', '').strip()
        location = kwargs.get('location', '').strip()

        params: dict = {}

        if query_type == 'email':
            params['email'] = query
            if name:
                params['name'] = name
            if company:
                params['company'] = company
            if location:
                params['location'] = location

        elif query_type == 'phone':
            params['phone'] = query
            if name:
                params['name'] = name
            if company:
                params['company'] = company
            if location:
                params['location'] = location

        elif query_type == 'social_profile':
            params['profile'] = query

        else:
            # username / other / auto — treat query as name or use explicit name
            params['name'] = name or query
            if company:
                params['company'] = company
            if location:
                params['location'] = location

        try:
            result = service.enrich_person(**params)
            result['query'] = query
            result['query_type'] = query_type
            return result
        except Exception as e:
            import traceback
            logger.error(f"PDL person enrichment error for '{query}': {e}\n{traceback.format_exc()}")
            return {
                'success': False,
                'error': str(e),
                'query': query,
            }


# Plugin instance (loaded by pluggy at startup)
plugin = PDLPersonEnrichPlugin()
