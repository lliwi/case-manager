"""
PeopleDataLabs (PDL) API Service for person enrichment.

Retrieves social media profiles, employment history, and contact information
for a person using PeopleDataLabs Person Enrichment API v5.
"""
import requests
from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class PDLService:
    """
    Service class for interacting with PeopleDataLabs API.

    Supports:
    - Person enrichment by name + company, email, phone, or social profile URL
    - Returns social profiles, employment, locations, emails, phones
    - Connection testing
    - Usage tracking
    """

    BASE_URL = "https://api.peopledatalabs.com/v5"
    PERSON_ENRICH_ENDPOINT = "/person/enrich"

    # Bootstrap Icons per social network
    NETWORK_ICONS = {
        'linkedin': 'bi-linkedin',
        'twitter': 'bi-twitter-x',
        'facebook': 'bi-facebook',
        'github': 'bi-github',
        'instagram': 'bi-instagram',
        'youtube': 'bi-youtube',
        'angellist': 'bi-briefcase',
        'gravatar': 'bi-person-circle',
        'aboutme': 'bi-person',
        'foursquare': 'bi-geo-alt',
        'xing': 'bi-people',
        'pinterest': 'bi-pinterest',
        'flickr': 'bi-image',
        'spotify': 'bi-spotify',
        'skype': 'bi-skype',
    }

    # Human-readable labels per network
    NETWORK_LABELS = {
        'linkedin': 'LinkedIn',
        'twitter': 'X (Twitter)',
        'facebook': 'Facebook',
        'github': 'GitHub',
        'instagram': 'Instagram',
        'youtube': 'YouTube',
        'angellist': 'AngelList',
        'gravatar': 'Gravatar',
        'aboutme': 'About.me',
        'foursquare': 'Foursquare',
        'xing': 'Xing',
        'pinterest': 'Pinterest',
        'flickr': 'Flickr',
        'spotify': 'Spotify',
        'skype': 'Skype',
    }

    def __init__(self, api_key_model):
        """
        Initialize the service with an ApiKey model instance.

        Args:
            api_key_model: ApiKey model instance (decrypts key internally)
        """
        self.api_key_model = api_key_model
        self.api_key = api_key_model.get_api_key()
        self.timeout = 15

    def enrich_person(
        self,
        name: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        company: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        profile: Optional[str] = None,
        location: Optional[str] = None,
        min_likelihood: int = 2,
    ) -> Dict[str, Any]:
        """
        Enrich person data using the PDL Person Enrichment API.

        At least one identifying parameter must be provided. For best results
        when using name, provide company or location as well.

        Args:
            name: Full name (e.g. "John Smith")
            first_name: Given name
            last_name: Family name
            company: Current or past employer name
            email: Email address
            phone: Phone number (with country code, e.g. "+34612345678")
            profile: Social media profile URL
            location: Living location (city, region, or country)
            min_likelihood: Minimum match confidence (2-10, default 2)

        Returns:
            dict with 'success', and either result fields or 'error'
        """
        params: Dict[str, Any] = {
            'min_likelihood': min_likelihood,
            'pretty': False,
            'include_if_matched': True,
        }

        if name:
            params['name'] = name
        if first_name:
            params['first_name'] = first_name
        if last_name:
            params['last_name'] = last_name
        if company:
            params['company'] = company
        if email:
            params['email'] = email
        if phone:
            params['phone'] = phone
        if profile:
            params['profile'] = profile
        if location:
            params['location'] = location

        headers = {
            'X-Api-Key': self.api_key,
            'Content-Type': 'application/json',
        }

        try:
            response = requests.get(
                f"{self.BASE_URL}{self.PERSON_ENRICH_ENDPOINT}",
                params=params,
                headers=headers,
                timeout=self.timeout,
            )

            if response.status_code == 200:
                raw = response.json()
                self.api_key_model.increment_usage()
                return self._process_response(raw)

            elif response.status_code == 404:
                return {
                    'success': False,
                    'error': 'No se encontró ningún perfil para los datos proporcionados.',
                    'status_code': 404,
                }
            elif response.status_code == 401:
                return {
                    'success': False,
                    'error': 'API Key de PeopleDataLabs inválida o sin permisos.',
                    'status_code': 401,
                }
            elif response.status_code == 402:
                return {
                    'success': False,
                    'error': 'Créditos de PeopleDataLabs agotados.',
                    'status_code': 402,
                }
            elif response.status_code == 429:
                return {
                    'success': False,
                    'error': 'Límite de tasa de PDL excedido. Intente de nuevo en unos momentos.',
                    'status_code': 429,
                }
            else:
                error_msg = 'Error desconocido'
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', {}).get('message', error_msg)
                except Exception:
                    pass
                return {
                    'success': False,
                    'error': f'Error de API PDL ({response.status_code}): {error_msg}',
                    'status_code': response.status_code,
                }

        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Tiempo de espera agotado al contactar con PeopleDataLabs API.',
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"PDL API request error: {str(e)}")
            return {
                'success': False,
                'error': f'Error de conexión: {str(e)}',
            }

    @staticmethod
    def _as_list(value) -> list:
        """Return value if it is a list, otherwise return [].

        PDL returns JSON false (Python bool False) for empty array fields
        instead of null/[], so `value or []` would yield False itself.
        """
        return value if isinstance(value, list) else []

    def _process_response(self, raw: Dict) -> Dict[str, Any]:
        """
        Normalise the raw PDL API response into a consistent structure.

        Args:
            raw: Raw JSON response from PDL API

        Returns:
            dict: Normalised person data
        """
        raw_data = raw.get('data')
        data = raw_data if isinstance(raw_data, dict) else {}
        likelihood = raw.get('likelihood', 0)
        matched = self._as_list(raw.get('matched'))

        # --- Social profiles array ---
        profiles = []
        for p in self._as_list(data.get('profiles')):
            network = (p.get('network') or '').lower()
            raw_url = p.get('url') or ''
            url = ('https://' + raw_url) if raw_url and not raw_url.startswith('http') else raw_url
            profiles.append({
                'network': network,
                'label': self.NETWORK_LABELS.get(network, network.title()),
                'url': url,
                'username': p.get('username') or '',
                'id': p.get('id') or '',
                'first_seen': p.get('first_seen') or '',
                'last_seen': p.get('last_seen') or '',
                'num_sources': p.get('num_sources') or 0,
                'icon': self.NETWORK_ICONS.get(network, 'bi-globe'),
            })

        # Sort: profiles with a URL first
        profiles.sort(key=lambda p: (0 if p['url'] else 1, p['network']))

        # --- Dedicated social URL/username fields ---
        social_links = {}
        for field in [
            'linkedin_url', 'twitter_url', 'facebook_url', 'github_url',
            'linkedin_username', 'twitter_username', 'facebook_username', 'github_username',
            'facebook_id', 'linkedin_id',
        ]:
            if data.get(field):
                social_links[field] = data[field]

        # --- Employment ---
        experience = []
        for exp in self._as_list(data.get('experience'))[:5]:
            company_info = exp.get('company')
            company_info = company_info if isinstance(company_info, dict) else {}
            title_info = exp.get('title')
            title_info = title_info if isinstance(title_info, dict) else {}
            experience.append({
                'title': title_info.get('name') or '',
                'company': company_info.get('name') or '',
                'company_size': company_info.get('size') or '',
                'is_primary': exp.get('is_primary', False),
                'start_date': exp.get('start_date') or '',
                'end_date': exp.get('end_date') or '',
                'current': not exp.get('end_date'),
                'type': exp.get('type') or '',
            })

        # --- Locations ---
        locations = []
        for loc in self._as_list(data.get('locations'))[:3]:
            locations.append({
                'name': loc.get('name') or '',
                'locality': loc.get('locality') or '',
                'region': loc.get('region') or '',
                'country': loc.get('country') or '',
                'is_primary': loc.get('is_primary', False),
            })

        # --- Emails ---
        emails = [
            e.get('address', '')
            for e in self._as_list(data.get('emails'))
            if e.get('address')
        ]

        # --- Phone numbers ---
        phones = [
            p.get('number', '')
            for p in self._as_list(data.get('phone_numbers'))
            if p.get('number')
        ]

        # --- Education ---
        education = []
        for edu in self._as_list(data.get('education'))[:3]:
            school_info = edu.get('school')
            school_info = school_info if isinstance(school_info, dict) else {}
            education.append({
                'school': school_info.get('name') or '',
                'degrees': self._as_list(edu.get('degrees')),
                'start_date': edu.get('start_date') or '',
                'end_date': edu.get('end_date') or '',
            })

        return {
            'success': True,
            'likelihood': likelihood,
            'likelihood_pct': int((likelihood / 10) * 100),
            'matched_fields': matched,
            # Identity
            'full_name': data.get('full_name') or '',
            'first_name': data.get('first_name') or '',
            'last_name': data.get('last_name') or '',
            'gender': data.get('gender') or '',
            'birth_year': data.get('birth_year'),
            # Current job
            'industry': data.get('industry') or '',
            'job_title': data.get('job_title') or '',
            'job_company_name': data.get('job_company_name') or '',
            'job_company_website': data.get('job_company_website') or '',
            # Social
            'profiles': profiles,
            'social_links': social_links,
            # History
            'experience': experience,
            'locations': locations,
            'emails': emails,
            'phones': phones,
            'education': education,
            # Bio
            'summary': data.get('summary') or '',
            # Raw for audit
            'raw_data': data,
        }

    def test_connection(self) -> Dict[str, Any]:
        """
        Test the PDL API key validity with a minimal request.

        Returns:
            dict with 'success' and 'message' or 'error'
        """
        try:
            response = requests.get(
                f"{self.BASE_URL}{self.PERSON_ENRICH_ENDPOINT}",
                params={'email': 'test@example.com', 'min_likelihood': 2},
                headers={'X-Api-Key': self.api_key},
                timeout=10,
            )
            # 200 = found, 404 = not found — both mean the key is valid
            if response.status_code in [200, 404]:
                return {'success': True, 'message': 'Conexión con PeopleDataLabs API exitosa.'}
            elif response.status_code == 401:
                return {'success': False, 'error': 'API Key inválida o sin permisos.'}
            elif response.status_code == 402:
                return {'success': False, 'error': 'Créditos agotados.'}
            else:
                return {'success': False, 'error': f'Respuesta inesperada: HTTP {response.status_code}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
