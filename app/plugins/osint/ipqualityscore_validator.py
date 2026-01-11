"""
IPQualityScore Email and Phone Validator Plugin.

OSINT plugin for validating emails and phone numbers using the IPQualityScore API.
Detects fraud, disposable emails, VOIP numbers, and provides risk assessment.
"""
import re
import pluggy
from app.models.api_key import ApiKey
from app.services.ipqualityscore_service import IPQualityScoreService
import logging

hookimpl = pluggy.HookimplMarker("casemanager")
logger = logging.getLogger(__name__)


class IPQualityScoreValidatorPlugin:
    """
    OSINT plugin for email and phone validation using IPQualityScore API.

    Features:
    - Email validation with fraud detection
    - Phone number validation and carrier lookup
    - Risk scoring and abuse detection
    - Disposable email detection
    - VOIP and temporary number detection
    """

    @hookimpl
    def get_info(self):
        """Get plugin information."""
        return {
            'name': 'ipqualityscore_validator',
            'display_name': 'IPQualityScore - Validador Email/Teléfono',
            'description': 'Valida emails y teléfonos usando IPQualityScore. Detecta fraude, emails temporales, números VOIP y proporciona análisis de riesgo.',
            'version': '1.0.0',
            'author': 'Case Manager',
            'category': 'osint',
            'type': 'validator',
            'supported_formats': ['email', 'phone'],
            'requires_api_key': True,
            'api_service': 'ipqualityscore'
        }

    @hookimpl
    def lookup(self, query: str, query_type: str = 'auto') -> dict:
        """
        Perform OSINT lookup on email or phone number.

        Args:
            query: Email address or phone number to validate
            query_type: Type of query ('email', 'phone', or 'auto' to detect)

        Returns:
            dict: Validation results with fraud analysis
        """
        # Get active API key
        api_key = ApiKey.get_active_key('ipqualityscore')

        if not api_key:
            return {
                'success': False,
                'error': 'No hay API Key activa configurada para IPQualityScore',
                'query': query,
                'recommendation': 'Configura una API Key en el panel de administración'
            }

        # Initialize service
        service = IPQualityScoreService(api_key)

        # Auto-detect query type if needed
        if query_type == 'auto':
            query_type = self._detect_query_type(query)

        # Validate based on type
        try:
            if query_type == 'email':
                return self._validate_email(service, query)
            elif query_type == 'phone':
                return self._validate_phone(service, query)
            else:
                return {
                    'success': False,
                    'error': f'Tipo de consulta no soportado: {query_type}',
                    'query': query
                }
        except Exception as e:
            logger.error(f"Error in IPQualityScore lookup for {query}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'query': query,
                'query_type': query_type
            }

    def _detect_query_type(self, query: str) -> str:
        """
        Auto-detect if query is an email or phone number.

        Args:
            query: Query string

        Returns:
            str: 'email', 'phone', or 'unknown'
        """
        # Clean query
        query = query.strip()

        # Check for email pattern
        email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        if email_pattern.match(query):
            return 'email'

        # Check for phone pattern (digits, spaces, dashes, parentheses, plus)
        phone_pattern = re.compile(r'^[\d\s\-\(\)\+]+$')
        if phone_pattern.match(query) and len(re.sub(r'[^\d]', '', query)) >= 7:
            return 'phone'

        return 'unknown'

    def _validate_email(self, service: IPQualityScoreService, email: str) -> dict:
        """
        Validate an email address.

        Args:
            service: IPQualityScore service instance
            email: Email address to validate

        Returns:
            dict: Validation results
        """
        try:
            result = service.validate_email(email, strict=True)

            # Build response
            response = {
                'success': True,
                'query': email,
                'query_type': 'email',
                'valid': result.get('valid', False),
                'fraud_score': result.get('fraud_score', 0),
                'overall_score': result.get('overall_score', 0),
                'interpretation': result.get('interpretation', {}),

                # Email-specific fields
                'disposable': result.get('disposable', False),
                'smtp_score': result.get('smtp_score', 0),
                'catch_all': result.get('catch_all', False),
                'generic': result.get('generic', False),
                'common': result.get('common', False),
                'dns_valid': result.get('dns_valid', False),
                'honeypot': result.get('honeypot', False),
                'deliverability': result.get('deliverability', 'unknown'),
                'frequent_complainer': result.get('frequent_complainer', False),
                'spam_trap_score': result.get('spam_trap_score', 'none'),
                'suspect': result.get('suspect', False),
                'recent_abuse': result.get('recent_abuse', False),
                'leaked': result.get('leaked', False),
                'domain_age': result.get('domain_age', {}),
                'first_name': result.get('first_name', ''),
                'suggested_domain': result.get('suggested_domain', ''),

                # Metadata
                'request_id': result.get('request_id', ''),
            }

            # Add risk summary
            response['risk_summary'] = service.get_risk_summary(result)

            return response

        except Exception as e:
            logger.error(f"Error validating email {email}: {str(e)}")
            raise

    def _validate_phone(self, service: IPQualityScoreService, phone: str) -> dict:
        """
        Validate a phone number.

        Args:
            service: IPQualityScore service instance
            phone: Phone number to validate

        Returns:
            dict: Validation results
        """
        try:
            # Try to detect country from phone format
            country = self._detect_country_code(phone)

            result = service.validate_phone(phone, country=country)

            # Build response
            response = {
                'success': True,
                'query': phone,
                'query_type': 'phone',
                'valid': result.get('valid', False),
                'fraud_score': result.get('fraud_score', 0),
                'interpretation': result.get('interpretation', {}),

                # Phone-specific fields
                'formatted': result.get('formatted', phone),
                'local_format': result.get('local_format', ''),
                'country': result.get('country', ''),
                'region': result.get('region', ''),
                'city': result.get('city', ''),
                'zip_code': result.get('zip_code', ''),
                'timezone': result.get('timezone', ''),
                'dialing_code': result.get('dialing_code', 0),

                # Line information
                'active': result.get('active', False),
                'active_status': result.get('active_status', 'unknown'),
                'line_type': result.get('line_type', 'unknown'),
                'carrier': result.get('carrier', 'unknown'),
                'carrier_mcc': result.get('carrier_mcc', ''),
                'carrier_mnc': result.get('carrier_mnc', ''),

                # Risk indicators
                'VOIP': result.get('VOIP', False),
                'prepaid': result.get('prepaid', False),
                'risky': result.get('risky', False),
                'recent_abuse': result.get('recent_abuse', False),
                'do_not_call': result.get('do_not_call', False),
                'leaked': result.get('leaked', False),

                # Associated data
                'name': result.get('name', ''),
                'associated_email_addresses': result.get('associated_email_addresses', {}),

                # Metadata
                'request_id': result.get('request_id', ''),
            }

            # Add risk summary
            response['risk_summary'] = service.get_risk_summary(result)

            return response

        except Exception as e:
            logger.error(f"Error validating phone {phone}: {str(e)}")
            raise

    def _detect_country_code(self, phone: str) -> str:
        """
        Try to detect country code from phone number.

        Args:
            phone: Phone number

        Returns:
            str: Two-letter country code or empty string
        """
        # Clean phone number
        clean_phone = re.sub(r'[^\d+]', '', phone)

        # Common country codes
        country_codes = {
            '+34': 'ES',  # Spain
            '+1': 'US',   # USA/Canada
            '+44': 'GB',  # UK
            '+33': 'FR',  # France
            '+49': 'DE',  # Germany
            '+39': 'IT',  # Italy
            '+351': 'PT', # Portugal
            '+52': 'MX',  # Mexico
            '+54': 'AR',  # Argentina
            '+55': 'BR',  # Brazil
        }

        for code, country in country_codes.items():
            if clean_phone.startswith(code):
                return country

        # If no country code detected, default to Spain (since this is for Spanish detectives)
        if not clean_phone.startswith('+') and len(clean_phone) == 9:
            return 'ES'

        return ''

    def validate(self, query: str, query_type: str = 'auto') -> dict:
        """
        Alias for lookup() to maintain compatibility with validator interface.

        Args:
            query: Email address or phone number
            query_type: Type of query ('email', 'phone', or 'auto')

        Returns:
            dict: Validation results
        """
        return self.lookup(query, query_type)


# Plugin instance
plugin = IPQualityScoreValidatorPlugin()
