"""
Instagram Profile Lookup Plugin.

OSINT plugin for retrieving Instagram user profiles using Apify's Instagram API Scraper.
Provides profile information including bio, followers, posts count, and verification status.
"""
import pluggy
from app.models.api_key import ApiKey
from app.services.apify_service import ApifyService
import logging

hookimpl = pluggy.HookimplMarker("casemanager")
logger = logging.getLogger(__name__)


class InstagramProfileLookupPlugin:
    """
    OSINT plugin for Instagram profile retrieval using Apify API.

    Features:
    - Profile information (username, full name, bio)
    - Follower/following counts
    - Post count
    - Verification status
    - Business account detection
    - Profile picture URL
    """

    @hookimpl
    def get_info(self):
        """Get plugin information."""
        return {
            'name': 'instagram_profile_lookup',
            'display_name': 'Instagram - Perfil de Usuario',
            'description': 'Obtiene información del perfil de un usuario de Instagram incluyendo biografía, seguidores, posts y estado de verificación usando Apify API.',
            'version': '1.0.0',
            'author': 'Case Manager',
            'category': 'osint',
            'type': 'social_media',
            'supported_formats': ['social_profile', 'username'],
            'requires_api_key': True,
            'api_service': 'apify'
        }

    @hookimpl
    def lookup(self, query: str, query_type: str = 'auto') -> dict:
        """
        Perform OSINT lookup to retrieve Instagram profile information.

        Args:
            query: Instagram username, profile URL, or handle
            query_type: Type of query ('username', 'social_profile', or 'auto')

        Returns:
            dict: User profile information with analysis
        """
        # Get active API key
        api_key = ApiKey.get_active_key('apify')

        if not api_key:
            return {
                'success': False,
                'error': 'No hay API Key activa configurada para Apify',
                'query': query,
                'recommendation': 'Configura un API Token de Apify en el panel de administración'
            }

        # Initialize service
        service = ApifyService(api_key)

        # Extract username from query
        username = self._extract_username(query)

        if not username:
            return {
                'success': False,
                'error': 'No se pudo extraer un nombre de usuario válido de la consulta',
                'query': query,
                'recommendation': 'Proporciona un nombre de usuario, handle (@usuario) o URL de perfil válida'
            }

        # Perform lookup
        try:
            result = service.scrape_instagram_profile(username)

            # Enhance result with additional analysis
            if result['success']:
                profile = result['data']

                # Build enhanced response
                enhanced_result = {
                    'success': True,
                    'query': query,
                    'query_type': 'instagram_profile',
                    'platform': 'Instagram',

                    # Profile data
                    'profile': profile,

                    # Analysis
                    'analysis': self._analyze_profile(profile),

                    # Raw data
                    'raw_data': result
                }

                return enhanced_result

            return result

        except Exception as e:
            logger.error(f"Error in Instagram profile lookup for {username}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'query': query,
                'username': username
            }

    def _extract_username(self, query: str) -> str:
        """
        Extract Instagram username from various input formats.

        Args:
            query: Username, URL, or handle

        Returns:
            str: Clean username without @ or URL parts
        """
        query = query.strip()

        # Remove @ if present
        if query.startswith('@'):
            query = query[1:]

        # Extract from URL
        if 'instagram.com' in query.lower():
            # Handle various Instagram URL formats
            # https://www.instagram.com/username/
            # https://instagram.com/username
            # www.instagram.com/username/
            parts = query.split('instagram.com/')
            if len(parts) > 1:
                username = parts[1].split('/')[0].split('?')[0]
                return username

        # Already a clean username
        return query

    def _analyze_profile(self, profile: dict) -> dict:
        """
        Analyze Instagram profile and generate insights.

        Args:
            profile: Profile data dict

        Returns:
            dict: Analysis results with credibility assessment
        """
        followers = profile.get('followers_count', 0)
        following = profile.get('following_count', 0)
        posts = profile.get('posts_count', 0)
        is_verified = profile.get('is_verified', False)
        is_private = profile.get('is_private', False)
        is_business = profile.get('is_business', False)

        # Calculate follower/following ratio
        ratio = followers / following if following > 0 else followers

        # Determine account type
        if is_verified:
            account_type = 'Cuenta Verificada'
            credibility = 'very_high'
            credibility_emoji = '🟢'
        elif is_business:
            account_type = 'Cuenta de Negocio'
            credibility = 'high'
            credibility_emoji = '🟢'
        elif followers > 10000:
            account_type = 'Influencer / Cuenta Grande'
            credibility = 'high'
            credibility_emoji = '🟢'
        elif followers > 1000:
            account_type = 'Cuenta Activa'
            credibility = 'medium'
            credibility_emoji = '🟡'
        else:
            account_type = 'Cuenta Personal'
            credibility = 'low'
            credibility_emoji = '⚪'

        # Activity level
        if posts > 500:
            activity = 'muy activa'
        elif posts > 100:
            activity = 'activa'
        elif posts > 10:
            activity = 'moderadamente activa'
        else:
            activity = 'poca actividad'

        # Build summary text
        summary_parts = []

        if is_verified:
            summary_parts.append('✓ Cuenta verificada')
        if is_private:
            summary_parts.append('cuenta privada')
        if is_business:
            summary_parts.append('cuenta de negocio')

        summary_parts.append(f'{self._format_number(followers)} seguidores')
        summary_parts.append(f'{posts} publicaciones')
        summary_parts.append(activity)
        summary_parts.append(f'credibilidad: {credibility} {credibility_emoji}')

        return {
            'text': ' | '.join(summary_parts),
            'account_type': account_type,
            'credibility': credibility,
            'credibility_emoji': credibility_emoji,
            'activity_level': activity,
            'follower_ratio': round(ratio, 2),
            'is_verified': is_verified,
            'is_private': is_private,
            'is_business': is_business,
            'engagement_potential': 'high' if followers > 10000 else 'medium' if followers > 1000 else 'low'
        }

    def _format_number(self, num: int) -> str:
        """Format large numbers in human-readable format."""
        if num >= 1_000_000:
            return f"{num/1_000_000:.1f}M"
        elif num >= 1_000:
            return f"{num/1_000:.1f}K"
        return str(num)


# Plugin instance
plugin = InstagramProfileLookupPlugin()
