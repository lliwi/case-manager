"""
X (Twitter) Profile Lookup Plugin.

OSINT plugin for retrieving user profile information from X (Twitter) using the official X API v2.
Provides detailed profile data including bio, metrics, verification status, and activity analysis.
"""
import pluggy
from app.models.api_key import ApiKey
from app.services.x_api_service import XAPIService
import logging

hookimpl = pluggy.HookimplMarker("casemanager")
logger = logging.getLogger(__name__)


class XProfileLookupPlugin:
    """
    OSINT plugin for X (Twitter) profile lookup using X API v2.

    Features:
    - User profile information retrieval
    - Account verification status
    - Follower and following metrics
    - Bio and location data
    - Profile credibility analysis
    - Account activity assessment
    """

    @hookimpl
    def get_info(self):
        """Get plugin information."""
        return {
            'name': 'x_profile_lookup',
            'display_name': 'X (Twitter) - Información de Perfil',
            'description': 'Obtiene información detallada de perfiles de X (Twitter) usando la API oficial. Incluye métricas, verificación, bio, ubicación y análisis de credibilidad.',
            'version': '1.0.0',
            'author': 'Case Manager',
            'category': 'osint',
            'type': 'social_media',
            'supported_formats': ['social_profile', 'username'],
            'requires_api_key': True,
            'api_service': 'x_api'
        }

    @hookimpl
    def lookup(self, query: str, query_type: str = 'auto') -> dict:
        """
        Perform OSINT lookup on X (Twitter) user profile.

        Args:
            query: Twitter username, profile URL, or handle
            query_type: Type of query ('username', 'social_profile', or 'auto')

        Returns:
            dict: Profile information and analysis
        """
        # Get active API key
        api_key = ApiKey.get_active_key('x_api')

        if not api_key:
            return {
                'success': False,
                'error': 'No hay API Key activa configurada para X API',
                'query': query,
                'recommendation': 'Configura un Bearer Token de X API en el panel de administración'
            }

        # Initialize service
        service = XAPIService(api_key)

        # Extract username from query
        username = service.extract_username_from_url(query)

        if not username:
            return {
                'success': False,
                'error': 'No se pudo extraer un nombre de usuario válido de la consulta',
                'query': query,
                'recommendation': 'Proporciona un nombre de usuario, handle (@usuario) o URL de perfil válida'
            }

        # Perform lookup
        try:
            result = service.get_user_by_username(username, include_metrics=True)

            # Enhance result with additional formatting
            if result['success']:
                user_data = result['user']

                # Build enhanced response
                enhanced_result = {
                    'success': True,
                    'query': query,
                    'query_type': 'social_profile',
                    'platform': 'X (Twitter)',

                    # Basic profile info
                    'user_id': user_data.get('id'),
                    'username': user_data.get('username'),
                    'display_name': user_data.get('name'),
                    'profile_url': f"https://x.com/{user_data.get('username')}",

                    # Profile details
                    'bio': user_data.get('description', ''),
                    'location': user_data.get('location', ''),
                    'website': user_data.get('url', ''),
                    'profile_image': user_data.get('profile_image_url', ''),
                    'created_at': user_data.get('created_at', ''),

                    # Status flags
                    'verified': user_data.get('verified', False),
                    'protected': user_data.get('protected', False),

                    # Metrics
                    'metrics': user_data.get('public_metrics', {}),

                    # Analysis
                    'analysis': user_data.get('interpretation', {}),

                    # Raw data
                    'raw_data': user_data
                }

                # Add summary for display
                enhanced_result['summary'] = self._generate_summary(enhanced_result)

                return enhanced_result

            return result

        except Exception as e:
            logger.error(f"Error in X profile lookup for {username}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'query': query,
                'username': username
            }

    def _generate_summary(self, profile_data: dict) -> dict:
        """
        Generate a human-readable summary of the profile.

        Args:
            profile_data: Profile data from API

        Returns:
            dict: Summary information
        """
        metrics = profile_data.get('metrics', {})
        analysis = profile_data.get('analysis', {})

        # Safely convert metrics to int
        def safe_int(value, default=0):
            try:
                if isinstance(value, (int, float)):
                    return int(value)
                elif isinstance(value, str):
                    return int(float(value))
                return default
            except (ValueError, TypeError):
                return default

        followers = safe_int(metrics.get('followers_count', 0))
        following = safe_int(metrics.get('following_count', 0))
        tweets = safe_int(metrics.get('tweet_count', 0))
        listed = safe_int(metrics.get('listed_count', 0))

        # Format numbers
        def format_number(num):
            if num >= 1_000_000:
                return f"{num/1_000_000:.1f}M"
            elif num >= 1_000:
                return f"{num/1_000:.1f}K"
            return str(num)

        # Build summary
        summary = {
            'followers_formatted': format_number(followers),
            'following_formatted': format_number(following),
            'tweets_formatted': format_number(tweets),
            'listed_formatted': format_number(listed),

            'account_age': self._calculate_account_age(profile_data.get('created_at', '')),
            'account_type': analysis.get('account_type', 'unknown'),
            'credibility': analysis.get('credibility', 'unknown'),
            'activity_level': analysis.get('activity_level', 'unknown'),
            'follower_ratio': analysis.get('follower_ratio', 0),

            'is_verified': profile_data.get('verified', False),
            'is_protected': profile_data.get('protected', False),

            'has_location': bool(profile_data.get('location')),
            'has_website': bool(profile_data.get('website')),
            'has_bio': bool(profile_data.get('bio')),
        }

        # Generate text summary
        summary['text'] = self._build_text_summary(summary, profile_data)

        return summary

    def _calculate_account_age(self, created_at: str) -> dict:
        """
        Calculate account age from creation date.

        Args:
            created_at: ISO datetime string

        Returns:
            dict: Age information
        """
        from datetime import datetime

        if not created_at:
            return {'years': 0, 'months': 0, 'days': 0, 'text': 'Desconocido'}

        try:
            created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            now = datetime.now(created.tzinfo)
            delta = now - created

            years = delta.days // 365
            remaining_days = delta.days % 365
            months = remaining_days // 30
            days = remaining_days % 30

            if years > 0:
                text = f"{years} año{'s' if years > 1 else ''}"
                if months > 0:
                    text += f", {months} mes{'es' if months > 1 else ''}"
            elif months > 0:
                text = f"{months} mes{'es' if months > 1 else ''}"
            else:
                text = f"{days} día{'s' if days > 1 else ''}"

            return {
                'years': years,
                'months': months,
                'days': days,
                'text': text,
                'total_days': delta.days
            }

        except Exception:
            return {'years': 0, 'months': 0, 'days': 0, 'text': 'Error al calcular'}

    def _build_text_summary(self, summary: dict, profile_data: dict) -> str:
        """
        Build a text summary of the profile.

        Args:
            summary: Summary dict
            profile_data: Full profile data

        Returns:
            str: Text summary
        """
        parts = []

        # Account type
        if summary['is_verified']:
            parts.append("✓ Cuenta verificada")
        elif summary['account_type'] == 'influencer':
            parts.append("Cuenta influyente")
        elif summary['account_type'] == 'new_or_inactive':
            parts.append("Cuenta nueva o inactiva")

        # Activity
        activity_text = {
            'high': 'alta actividad',
            'medium': 'actividad media',
            'low': 'baja actividad'
        }.get(summary['activity_level'], 'actividad desconocida')
        parts.append(activity_text)

        # Metrics highlight
        try:
            followers_num = float(summary['followers_formatted'].rstrip('KM'))
            if followers_num > 10:
                parts.append(f"{summary['followers_formatted']} seguidores")
        except (ValueError, AttributeError):
            # If conversion fails, skip this part
            pass

        # Age
        parts.append(f"cuenta de {summary['account_age']['text']}")

        # Credibility
        cred_emoji = {
            'high': '🟢',
            'medium-high': '🟢',
            'medium': '🟡',
            'low': '🔴'
        }.get(summary['credibility'], '⚪')
        parts.append(f"credibilidad: {summary['credibility']} {cred_emoji}")

        return " | ".join(parts)


# Plugin instance
plugin = XProfileLookupPlugin()
