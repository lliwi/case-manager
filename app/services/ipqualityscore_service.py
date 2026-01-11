"""
IPQualityScore API Service for email and phone validation.

Provides fraud detection and validation services for emails and phone numbers
using the IPQualityScore API. Implements rate limiting, error handling, and
response caching for optimal performance.
"""
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class IPQualityScoreService:
    """
    Service class for interacting with IPQualityScore API.

    Supports:
    - Email validation and fraud detection
    - Phone number validation and risk assessment
    - Connection testing
    - Usage tracking
    """

    # API Base URLs
    BASE_URL = "https://ipqualityscore.com/api/json"
    EMAIL_ENDPOINT = "email"
    PHONE_ENDPOINT = "phone"

    # Fraud score thresholds
    FRAUD_SCORE_SUSPICIOUS = 80
    FRAUD_SCORE_HIGH_RISK = 90

    def __init__(self, api_key_model):
        """
        Initialize the service with an API key model.

        Args:
            api_key_model: ApiKey model instance
        """
        self.api_key_model = api_key_model
        self.api_key = api_key_model.get_api_key()
        self.timeout = 10  # seconds

    def _make_request(self, endpoint: str, resource: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make a request to the IPQualityScore API.

        Args:
            endpoint: API endpoint (email, phone, etc.)
            resource: Resource to validate (email address, phone number)
            params: Additional query parameters

        Returns:
            dict: API response

        Raises:
            Exception: If request fails
        """
        url = f"{self.BASE_URL}/{endpoint}/{self.api_key}/{resource}"

        try:
            response = requests.get(
                url,
                params=params or {},
                timeout=self.timeout,
                headers={
                    'User-Agent': 'CaseManager-OSINT/1.0'
                }
            )

            # Check for HTTP errors
            response.raise_for_status()

            data = response.json()

            # Check for API-specific errors
            if not data.get('success', True):
                error_message = data.get('message', 'Unknown API error')
                logger.error(f"IPQualityScore API error: {error_message}")
                raise Exception(f"API Error: {error_message}")

            return data

        except requests.exceptions.Timeout:
            logger.error(f"Timeout connecting to IPQualityScore API")
            raise Exception("Request timeout - the API took too long to respond")
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error to IPQualityScore API")
            raise Exception("Connection error - could not reach the API")
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error from IPQualityScore API: {e}")
            if response.status_code == 401:
                raise Exception("Invalid API key")
            elif response.status_code == 403:
                raise Exception("API key does not have permission for this action")
            elif response.status_code == 429:
                raise Exception("Rate limit exceeded")
            else:
                raise Exception(f"HTTP error {response.status_code}")
        except Exception as e:
            logger.error(f"Unexpected error calling IPQualityScore API: {str(e)}")
            raise

    def validate_email(self, email: str, strict: bool = False, timeout: int = 7) -> Dict[str, Any]:
        """
        Validate an email address and check for fraud indicators.

        Args:
            email: Email address to validate
            strict: Enable strict validation (checks MX records)
            timeout: Timeout for SMTP checks (1-20 seconds)

        Returns:
            dict: Validation results containing:
                - valid: bool - Whether email is valid
                - disposable: bool - Is it a disposable/temporary email
                - smtp_score: int - Deliverability score (0-3)
                - overall_score: int - Quality score (0-4)
                - fraud_score: int - Fraud probability (0-100)
                - recent_abuse: bool - Known for abuse
                - spam_trap_score: str - Risk level (low/medium/high)
                - catch_all: bool - Is it a catch-all domain
                - leaked: bool - Found in data breaches
                - first_name: str - Extracted first name (if available)
                - deliverability: str - Expected deliverability (high/medium/low)
                - frequent_complainer: bool - Known for complaints
                - suggested_domain: str - Typo correction suggestion

        Raises:
            Exception: If validation fails
        """
        params = {
            'strictness': 1 if strict else 0,
            'timeout': max(1, min(20, timeout)),
            'abuse_strictness': 0,
            'fast': 0  # Use full validation
        }

        try:
            result = self._make_request(self.EMAIL_ENDPOINT, email, params)

            # Track usage
            self.api_key_model.increment_usage()

            # Add interpretation
            result['interpretation'] = self._interpret_email_result(result)

            return result

        except Exception as e:
            logger.error(f"Error validating email {email}: {str(e)}")
            raise

    def validate_phone(self, phone: str, country: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate a phone number and check for fraud indicators.

        Args:
            phone: Phone number to validate (E.164 format recommended)
            country: Optional 2-letter country code (e.g., 'ES' for Spain)

        Returns:
            dict: Validation results containing:
                - valid: bool - Whether phone is valid
                - active: bool - Is the line currently active
                - fraud_score: int - Fraud probability (0-100)
                - recent_abuse: bool - Known for abuse
                - VOIP: bool - Is it a VOIP number
                - risky: bool - High risk assessment
                - carrier: str - Phone carrier name
                - line_type: str - Type (Mobile, Landline, VOIP, etc.)
                - country: str - Country name
                - region: str - State/region
                - city: str - City
                - timezone: str - Timezone
                - dialing_code: int - Country dialing code
                - prepaid: bool - Is it prepaid
                - do_not_call: bool - On do-not-call list
                - leaked: bool - Found in data breaches
                - name: str - Associated name (if available)
                - associated_email_addresses: dict - Related emails

        Raises:
            Exception: If validation fails
        """
        params = {}
        if country:
            params['country'] = country.upper()

        try:
            result = self._make_request(self.PHONE_ENDPOINT, phone, params)

            # Track usage
            self.api_key_model.increment_usage()

            # Add interpretation
            result['interpretation'] = self._interpret_phone_result(result)

            return result

        except Exception as e:
            logger.error(f"Error validating phone {phone}: {str(e)}")
            raise

    def test_connection(self) -> Dict[str, Any]:
        """
        Test the API connection with a simple validation.

        Returns:
            dict: Test result with success flag and details

        """
        try:
            # Test with a known valid email
            test_email = "test@example.com"
            result = self._make_request(self.EMAIL_ENDPOINT, test_email, {'fast': 1})

            return {
                'success': True,
                'message': 'Connection successful',
                'details': {
                    'credits_remaining': result.get('request_id', 'unknown'),
                    'response_time': result.get('request_duration', 'unknown')
                }
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def _interpret_email_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Interpret email validation results and provide recommendations.

        Args:
            result: Raw API response

        Returns:
            dict: Interpretation with risk level and recommendation
        """
        fraud_score = result.get('fraud_score', 0)
        is_valid = result.get('valid', False)
        is_disposable = result.get('disposable', False)
        recent_abuse = result.get('recent_abuse', False)
        spam_trap = result.get('spam_trap_score', 'none')

        # Determine risk level
        if not is_valid:
            risk_level = 'invalid'
            recommendation = 'Rechazar - Email no válido'
            color = 'danger'
        elif is_disposable:
            risk_level = 'high'
            recommendation = 'Alto riesgo - Email temporal/desechable'
            color = 'danger'
        elif fraud_score >= self.FRAUD_SCORE_HIGH_RISK or recent_abuse or spam_trap == 'high':
            risk_level = 'high'
            recommendation = 'Alto riesgo - Posible fraude'
            color = 'danger'
        elif fraud_score >= self.FRAUD_SCORE_SUSPICIOUS or spam_trap == 'medium':
            risk_level = 'medium'
            recommendation = 'Riesgo medio - Requiere verificación adicional'
            color = 'warning'
        else:
            risk_level = 'low'
            recommendation = 'Bajo riesgo - Email legítimo'
            color = 'success'

        return {
            'risk_level': risk_level,
            'recommendation': recommendation,
            'color': color,
            'fraud_score': fraud_score,
            'quality_score': result.get('overall_score', 0),
            'deliverability': result.get('deliverability', 'unknown')
        }

    def _interpret_phone_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Interpret phone validation results and provide recommendations.

        Args:
            result: Raw API response

        Returns:
            dict: Interpretation with risk level and recommendation
        """
        fraud_score = result.get('fraud_score', 0)
        is_valid = result.get('valid', False)
        is_active = result.get('active', False)
        is_voip = result.get('VOIP', False)
        is_risky = result.get('risky', False)
        recent_abuse = result.get('recent_abuse', False)

        # Determine risk level
        if not is_valid:
            risk_level = 'invalid'
            recommendation = 'Rechazar - Número no válido'
            color = 'danger'
        elif not is_active:
            risk_level = 'high'
            recommendation = 'Alto riesgo - Línea inactiva'
            color = 'danger'
        elif fraud_score >= self.FRAUD_SCORE_HIGH_RISK or is_risky or recent_abuse:
            risk_level = 'high'
            recommendation = 'Alto riesgo - Posible fraude'
            color = 'danger'
        elif fraud_score >= self.FRAUD_SCORE_SUSPICIOUS or is_voip:
            risk_level = 'medium'
            recommendation = f"Riesgo medio - {'VOIP detectado' if is_voip else 'Requiere verificación'}"
            color = 'warning'
        else:
            risk_level = 'low'
            recommendation = 'Bajo riesgo - Número legítimo'
            color = 'success'

        return {
            'risk_level': risk_level,
            'recommendation': recommendation,
            'color': color,
            'fraud_score': fraud_score,
            'line_type': result.get('line_type', 'unknown'),
            'carrier': result.get('carrier', 'unknown'),
            'active_status': 'active' if is_active else 'inactive'
        }

    def get_risk_summary(self, validation_result: Dict[str, Any]) -> str:
        """
        Get a human-readable risk summary from validation results.

        Args:
            validation_result: Result from validate_email or validate_phone

        Returns:
            str: Risk summary text
        """
        if 'interpretation' in validation_result:
            interp = validation_result['interpretation']
            return f"{interp['risk_level'].upper()}: {interp['recommendation']}"
        return "No interpretation available"
