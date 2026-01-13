"""
X (Twitter) Tweets Lookup Plugin.

OSINT plugin for retrieving recent tweets from X (Twitter) users using the official X API v2.
Provides tweet content, metrics, engagement analysis, and timeline data.
"""
import pluggy
from app.models.api_key import ApiKey
from app.services.x_api_service import XAPIService
import logging

hookimpl = pluggy.HookimplMarker("casemanager")
logger = logging.getLogger(__name__)


class XTweetsLookupPlugin:
    """
    OSINT plugin for X (Twitter) tweets retrieval using X API v2.

    Features:
    - Recent tweets retrieval (up to 100)
    - Tweet content and metadata
    - Engagement metrics (likes, retweets, replies)
    - Tweet type detection (original, retweet, reply, quote)
    - Language detection
    - Entity extraction (URLs, mentions, hashtags)
    - Engagement analysis
    """

    @hookimpl
    def get_info(self):
        """Get plugin information."""
        return {
            'name': 'x_tweets_lookup',
            'display_name': 'X (Twitter) - Últimos Tweets',
            'description': 'Obtiene los tweets más recientes de un usuario de X (Twitter) usando la API oficial. Incluye métricas de engagement, tipo de tweet y análisis de contenido.',
            'version': '1.0.0',
            'author': 'Case Manager',
            'category': 'osint',
            'type': 'social_media',
            'supported_formats': ['social_profile', 'username'],
            'requires_api_key': True,
            'api_service': 'x_api'
        }

    @hookimpl
    def lookup(self, query: str, query_type: str = 'auto', max_results: int = 10) -> dict:
        """
        Perform OSINT lookup to retrieve recent tweets from X (Twitter) user.

        Args:
            query: Twitter username, profile URL, or handle
            query_type: Type of query ('username', 'social_profile', or 'auto')
            max_results: Number of tweets to retrieve (5-100, default 10)

        Returns:
            dict: User profile and recent tweets with analysis
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

        # Validate max_results
        max_results = max(5, min(100, max_results))

        # Perform lookup
        try:
            result = service.get_user_tweets(username=username, max_results=max_results, include_metrics=True)

            # Enhance result with additional analysis
            if result['success']:
                user_data = result['user']
                tweets = result['tweets']

                # Build enhanced response
                enhanced_result = {
                    'success': True,
                    'query': query,
                    'query_type': 'tweets',
                    'platform': 'X (Twitter)',

                    # User info
                    'user': {
                        'id': user_data.get('id'),
                        'username': user_data.get('username'),
                        'display_name': user_data.get('name'),
                        'profile_url': f"https://x.com/{user_data.get('username')}",
                        'profile_image': user_data.get('profile_image_url', ''),
                        'verified': user_data.get('verified', False),
                    },

                    # Tweets data
                    'tweets': self._enhance_tweets(tweets, user_data.get('username')),
                    'tweet_count': len(tweets),
                    'requested_count': max_results,

                    # Analysis
                    'timeline_analysis': self._analyze_timeline(tweets),

                    # Metadata
                    'meta': result.get('meta', {}),

                    # Raw data
                    'raw_data': result
                }

                # Add summary
                enhanced_result['summary'] = self._generate_summary(enhanced_result)

                return enhanced_result

            return result

        except Exception as e:
            logger.error(f"Error in X tweets lookup for {username}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'query': query,
                'username': username
            }

    def _enhance_tweets(self, tweets: list, username: str) -> list:
        """
        Enhance tweets with additional formatting and URLs.

        Args:
            tweets: List of tweet objects
            username: Username of the profile

        Returns:
            list: Enhanced tweets
        """
        enhanced = []

        for tweet in tweets:
            tweet_id = tweet.get('id')
            enhanced_tweet = {
                'id': tweet_id,
                'url': f"https://x.com/{username}/status/{tweet_id}",
                'text': tweet.get('text', ''),
                'created_at': tweet.get('created_at', ''),
                'created_at_formatted': self._format_datetime(tweet.get('created_at', '')),

                # Metrics
                'metrics': tweet.get('public_metrics', {}),
                'metrics_formatted': self._format_metrics(tweet.get('public_metrics', {})),

                # Analysis from service
                'engagement': tweet.get('interpretation', {}),

                # Tweet type
                'is_retweet': tweet.get('interpretation', {}).get('is_retweet', False),
                'is_reply': tweet.get('interpretation', {}).get('is_reply', False),
                'is_quote': tweet.get('interpretation', {}).get('is_quote', False),

                # Language
                'language': tweet.get('lang', 'unknown'),

                # Entities
                'entities': tweet.get('entities', {}),
                'has_urls': bool(tweet.get('entities', {}).get('urls')),
                'has_mentions': bool(tweet.get('entities', {}).get('mentions')),
                'has_hashtags': bool(tweet.get('entities', {}).get('hashtags')),

                # Media (images, videos, GIFs)
                'media': tweet.get('media', []),

                # Raw data
                'raw': tweet
            }

            enhanced.append(enhanced_tweet)

        return enhanced

    def _format_datetime(self, datetime_str: str) -> str:
        """
        Format ISO datetime to human-readable Spanish format.

        Args:
            datetime_str: ISO datetime string

        Returns:
            str: Formatted datetime
        """
        from datetime import datetime

        if not datetime_str:
            return 'Desconocido'

        try:
            dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
            return dt.strftime('%d/%m/%Y %H:%M:%S')
        except Exception:
            return datetime_str

    def _format_metrics(self, metrics: dict) -> dict:
        """
        Format metrics with human-readable numbers.

        Args:
            metrics: Raw metrics dict

        Returns:
            dict: Formatted metrics
        """
        def safe_int(value, default=0):
            try:
                if isinstance(value, (int, float)):
                    return int(value)
                elif isinstance(value, str):
                    return int(float(value))
                return default
            except (ValueError, TypeError):
                return default

        def format_number(num):
            num = safe_int(num)
            if num >= 1_000_000:
                return f"{num/1_000_000:.1f}M"
            elif num >= 1_000:
                return f"{num/1_000:.1f}K"
            return str(num)

        return {
            'likes': format_number(metrics.get('like_count', 0)),
            'retweets': format_number(metrics.get('retweet_count', 0)),
            'replies': format_number(metrics.get('reply_count', 0)),
            'quotes': format_number(metrics.get('quote_count', 0)),
            'bookmarks': format_number(metrics.get('bookmark_count', 0)),
            'impressions': format_number(metrics.get('impression_count', 0)) if 'impression_count' in metrics else 'N/A'
        }

    def _analyze_timeline(self, tweets: list) -> dict:
        """
        Analyze the overall timeline and extract patterns.

        Args:
            tweets: List of tweet objects

        Returns:
            dict: Timeline analysis
        """
        if not tweets:
            return {
                'total_tweets': 0,
                'error': 'No hay tweets disponibles para analizar'
            }

        # Helper to safely convert values to int
        def safe_int(value, default=0):
            try:
                if isinstance(value, (int, float)):
                    return int(value)
                elif isinstance(value, str):
                    return int(float(value))
                return default
            except (ValueError, TypeError):
                return default

        # Count tweet types
        original_tweets = sum(1 for t in tweets if not t.get('interpretation', {}).get('is_retweet') and not t.get('interpretation', {}).get('is_reply'))
        retweets = sum(1 for t in tweets if t.get('interpretation', {}).get('is_retweet'))
        replies = sum(1 for t in tweets if t.get('interpretation', {}).get('is_reply'))
        quotes = sum(1 for t in tweets if t.get('interpretation', {}).get('is_quote'))

        # Calculate total engagement
        total_likes = sum(safe_int(t.get('public_metrics', {}).get('like_count', 0)) for t in tweets)
        total_retweets = sum(safe_int(t.get('public_metrics', {}).get('retweet_count', 0)) for t in tweets)
        total_replies = sum(safe_int(t.get('public_metrics', {}).get('reply_count', 0)) for t in tweets)
        total_engagement = total_likes + total_retweets + total_replies

        # Average engagement
        avg_engagement = total_engagement / len(tweets) if tweets else 0

        # Most engaged tweet
        most_engaged = max(tweets, key=lambda t: sum(safe_int(v) for v in t.get('public_metrics', {}).values())) if tweets else None

        # Language distribution
        languages = {}
        for tweet in tweets:
            lang = tweet.get('lang', 'unknown')
            languages[lang] = languages.get(lang, 0) + 1

        # Determine content type
        if original_tweets / len(tweets) > 0.7:
            content_type = 'original_content'
        elif retweets / len(tweets) > 0.5:
            content_type = 'mostly_retweets'
        elif replies / len(tweets) > 0.5:
            content_type = 'mostly_conversations'
        else:
            content_type = 'mixed'

        return {
            'total_tweets': len(tweets),
            'original_tweets': original_tweets,
            'retweets': retweets,
            'replies': replies,
            'quotes': quotes,

            'content_type': content_type,

            'total_engagement': total_engagement,
            'avg_engagement': round(avg_engagement, 1),

            'total_likes': total_likes,
            'total_retweets': total_retweets,
            'total_replies': total_replies,

            'most_engaged_tweet_id': most_engaged.get('id') if most_engaged else None,
            'most_engaged_tweet_engagement': sum(safe_int(v) for v in most_engaged.get('public_metrics', {}).values()) if most_engaged else 0,

            'languages': languages,
            'primary_language': max(languages.items(), key=lambda x: x[1])[0] if languages else 'unknown'
        }

    def _generate_summary(self, result: dict) -> dict:
        """
        Generate a human-readable summary of the timeline.

        Args:
            result: Full result dict

        Returns:
            dict: Summary information
        """
        analysis = result.get('timeline_analysis', {})
        user = result.get('user', {})
        tweet_count = result.get('tweet_count', 0)

        # Build text summary
        summary_parts = []

        # Tweet count
        summary_parts.append(f"{tweet_count} tweets analizados")

        # Content type
        content_type_text = {
            'original_content': 'contenido principalmente original',
            'mostly_retweets': 'mayormente retweets',
            'mostly_conversations': 'mayormente conversaciones',
            'mixed': 'contenido mixto'
        }.get(analysis.get('content_type', 'mixed'), 'contenido mixto')
        summary_parts.append(content_type_text)

        # Engagement
        avg_eng = analysis.get('avg_engagement', 0)
        if avg_eng > 1000:
            summary_parts.append(f"alto engagement ({avg_eng:.0f} promedio)")
        elif avg_eng > 100:
            summary_parts.append(f"engagement medio ({avg_eng:.0f} promedio)")
        else:
            summary_parts.append(f"bajo engagement ({avg_eng:.0f} promedio)")

        # Language
        primary_lang = analysis.get('primary_language', 'unknown')
        lang_names = {
            'es': 'español',
            'en': 'inglés',
            'ca': 'catalán',
            'fr': 'francés',
            'de': 'alemán',
            'it': 'italiano',
            'pt': 'portugués'
        }
        summary_parts.append(f"idioma: {lang_names.get(primary_lang, primary_lang)}")

        return {
            'text': ' | '.join(summary_parts),
            'content_type': analysis.get('content_type', 'mixed'),
            'avg_engagement': analysis.get('avg_engagement', 0),
            'total_engagement': analysis.get('total_engagement', 0),
            'primary_language': primary_lang,
            'user_verified': user.get('verified', False)
        }


# Plugin instance
plugin = XTweetsLookupPlugin()
