"""
Instagram Posts Lookup Plugin.

OSINT plugin for retrieving Instagram posts using Apify's Instagram API Scraper.
Provides post content, images, videos, engagement metrics, and timing analysis.
"""
import pluggy
from app.models.api_key import ApiKey
from app.services.apify_service import ApifyService
from datetime import datetime
import logging

hookimpl = pluggy.HookimplMarker("casemanager")
logger = logging.getLogger(__name__)


class InstagramPostsLookupPlugin:
    """
    OSINT plugin for Instagram posts retrieval using Apify API.

    Features:
    - Recent posts retrieval (up to 50)
    - Post content and captions
    - Images and videos
    - Engagement metrics (likes, comments)
    - Hashtags and mentions extraction
    - Location data (if available)
    - Posting patterns analysis
    """

    @hookimpl
    def get_info(self):
        """Get plugin information."""
        return {
            'name': 'instagram_posts_lookup',
            'display_name': 'Instagram - Posts de Usuario',
            'description': 'Obtiene los posts más recientes de un usuario de Instagram incluyendo imágenes, videos, captions, likes y comentarios usando Apify API.',
            'version': '1.0.0',
            'author': 'Case Manager',
            'category': 'osint',
            'type': 'social_media',
            'supported_formats': ['social_profile', 'username'],
            'requires_api_key': True,
            'api_service': 'apify'
        }

    @hookimpl
    def lookup(self, query: str, query_type: str = 'auto', max_posts: int = 12) -> dict:
        """
        Perform OSINT lookup to retrieve Instagram posts.

        Args:
            query: Instagram username, profile URL, or handle
            query_type: Type of query ('username', 'social_profile', or 'auto')
            max_posts: Maximum number of posts to retrieve (default 12, max 50)

        Returns:
            dict: Posts data with images, captions, engagement, and analysis
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

        # Validate max_posts
        max_posts = max(1, min(50, max_posts))

        # Perform lookup
        try:
            result = service.scrape_instagram_posts(username, max_posts)

            # Enhance result with additional analysis
            if result['success']:
                posts = result['posts']
                profile = result.get('profile')

                # Build enhanced response
                enhanced_result = {
                    'success': True,
                    'query': query,
                    'query_type': 'instagram_posts',
                    'platform': 'Instagram',

                    # Profile info (if available)
                    'profile': profile,

                    # Posts data
                    'posts': self._enhance_posts(posts, username),
                    'post_count': len(posts),
                    'requested_count': max_posts,

                    # Analysis
                    'posts_analysis': self._analyze_posts(posts),

                    # Raw data
                    'raw_data': result
                }

                # Add summary
                enhanced_result['summary'] = self._generate_summary(enhanced_result)

                return enhanced_result

            return result

        except Exception as e:
            logger.error(f"Error in Instagram posts lookup for {username}: {str(e)}")
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
            parts = query.split('instagram.com/')
            if len(parts) > 1:
                username = parts[1].split('/')[0].split('?')[0]
                return username

        return query

    def _enhance_posts(self, posts: list, username: str) -> list:
        """
        Enhance posts with additional formatting and metadata.

        Args:
            posts: List of post objects
            username: Username of the profile

        Returns:
            list: Enhanced posts
        """
        enhanced = []

        for post in posts:
            post_id = post.get('id')
            shortcode = post.get('shortcode')

            enhanced_post = {
                'id': post_id,
                'shortcode': shortcode,
                'type': post.get('type'),
                'url': post.get('url') or f"https://www.instagram.com/p/{shortcode}/",
                'caption': post.get('caption', ''),
                'hashtags': post.get('hashtags', []),
                'mentions': post.get('mentions', []),
                'timestamp': post.get('timestamp'),
                'timestamp_formatted': self._format_datetime(post.get('timestamp')),

                # Engagement
                'likes_count': post.get('likes_count', 0),
                'comments_count': post.get('comments_count', 0),
                'engagement_total': post.get('likes_count', 0) + post.get('comments_count', 0),

                # Media
                'display_url': post.get('display_url'),
                'images': post.get('images', []),
                'videos': post.get('videos', []),
                'has_video': bool(post.get('videos')),
                'is_carousel': bool(post.get('child_posts')),
                'carousel_count': len(post.get('child_posts', [])),

                # Metadata
                'dimensions': post.get('dimensions', {}),
                'location': post.get('location'),
                'owner': post.get('owner', {}),

                # Raw data
                'raw': post
            }

            enhanced.append(enhanced_post)

        return enhanced

    def _analyze_posts(self, posts: list) -> dict:
        """
        Analyze posts to extract patterns and insights.

        Args:
            posts: List of post objects

        Returns:
            dict: Analysis results
        """
        if not posts:
            return {
                'total_posts': 0,
                'error': 'No hay posts disponibles para analizar'
            }

        # Count post types
        images = sum(1 for p in posts if p.get('type') == 'Image')
        videos = sum(1 for p in posts if p.get('type') == 'Video')
        carousels = sum(1 for p in posts if p.get('type') == 'Sidecar')

        # Calculate engagement
        total_likes = sum(p.get('likes_count', 0) for p in posts)
        total_comments = sum(p.get('comments_count', 0) for p in posts)
        total_engagement = total_likes + total_comments
        avg_engagement = total_engagement / len(posts) if posts else 0

        # Hashtag analysis
        all_hashtags = []
        for post in posts:
            all_hashtags.extend(post.get('hashtags', []))

        hashtag_freq = {}
        for tag in all_hashtags:
            hashtag_freq[tag] = hashtag_freq.get(tag, 0) + 1

        top_hashtags = sorted(hashtag_freq.items(), key=lambda x: x[1], reverse=True)[:5]

        # Location analysis
        posts_with_location = sum(1 for p in posts if p.get('location'))

        # Determine content type
        if videos / len(posts) > 0.6:
            content_type = 'video_focused'
        elif carousels / len(posts) > 0.5:
            content_type = 'carousel_focused'
        else:
            content_type = 'mixed_content'

        return {
            'total_posts': len(posts),
            'post_types': {
                'images': images,
                'videos': videos,
                'carousels': carousels
            },
            'content_type': content_type,

            'total_engagement': total_engagement,
            'avg_engagement': round(avg_engagement, 1),
            'total_likes': total_likes,
            'total_comments': total_comments,
            'avg_likes': round(total_likes / len(posts), 1) if posts else 0,
            'avg_comments': round(total_comments / len(posts), 1) if posts else 0,

            'hashtag_usage': len(all_hashtags),
            'top_hashtags': [tag for tag, _ in top_hashtags],
            'posts_with_location': posts_with_location
        }

    def _generate_summary(self, result: dict) -> dict:
        """
        Generate a human-readable summary of the posts analysis.

        Args:
            result: Full result dict

        Returns:
            dict: Summary information
        """
        analysis = result.get('posts_analysis', {})
        post_count = result.get('post_count', 0)

        # Build text summary
        summary_parts = []

        # Post count
        summary_parts.append(f"{post_count} posts analizados")

        # Content type
        content_type_text = {
            'video_focused': 'contenido principalmente en video',
            'carousel_focused': 'mayormente carruseles',
            'mixed_content': 'contenido mixto'
        }.get(analysis.get('content_type', 'mixed_content'), 'contenido mixto')
        summary_parts.append(content_type_text)

        # Engagement
        avg_eng = analysis.get('avg_engagement', 0)
        if avg_eng > 1000:
            summary_parts.append(f"alto engagement ({avg_eng:.0f} promedio)")
        elif avg_eng > 100:
            summary_parts.append(f"engagement medio ({avg_eng:.0f} promedio)")
        else:
            summary_parts.append(f"bajo engagement ({avg_eng:.0f} promedio)")

        # Hashtags
        hashtag_count = analysis.get('hashtag_usage', 0)
        if hashtag_count > 0:
            summary_parts.append(f"{hashtag_count} hashtags usados")

        return {
            'text': ' | '.join(summary_parts),
            'content_type': analysis.get('content_type', 'mixed_content'),
            'avg_engagement': analysis.get('avg_engagement', 0),
            'total_engagement': analysis.get('total_engagement', 0),
            'top_hashtags': analysis.get('top_hashtags', [])
        }

    def _format_datetime(self, timestamp_str: str) -> str:
        """
        Format ISO datetime to human-readable Spanish format.

        Args:
            timestamp_str: ISO datetime string

        Returns:
            str: Formatted datetime
        """
        if not timestamp_str:
            return 'Desconocido'

        try:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return dt.strftime('%d/%m/%Y %H:%M:%S')
        except Exception:
            return timestamp_str


# Plugin instance
plugin = InstagramPostsLookupPlugin()
