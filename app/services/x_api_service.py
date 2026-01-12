"""
X API (Twitter API v2) Service for profile and tweet retrieval.

Provides user profile information and recent tweets using the X API v2.
Implements rate limiting, error handling, and response caching.
"""
import requests
from typing import Dict, Optional, Any, List
import logging
import re

logger = logging.getLogger(__name__)


class XAPIService:
    """
    Service class for interacting with X API (Twitter API v2).

    Supports:
    - User profile lookup by username
    - User profile lookup by user ID
    - Recent tweets retrieval
    - Connection testing
    - Usage tracking
    """

    # API Base URL
    BASE_URL = "https://api.x.com/2"

    # Endpoints
    USERS_BY_USERNAME = "users/by/username"
    USERS_BY_ID = "users"
    TWEETS_ENDPOINT = "tweets"
    USER_TWEETS_ENDPOINT = "users/{}/tweets"

    def __init__(self, api_key_model):
        """
        Initialize the service with an API key model.

        Args:
            api_key_model: ApiKey model instance containing bearer token
        """
        self.api_key_model = api_key_model
        self.bearer_token = api_key_model.get_api_key()
        self.timeout = 10  # seconds

    def _make_request(self, endpoint: str, params: Optional[Dict] = None, method: str = 'GET') -> Dict[str, Any]:
        """
        Make a request to the X API.

        Args:
            endpoint: API endpoint path
            params: Query parameters
            method: HTTP method (GET, POST, etc.)

        Returns:
            dict: API response

        Raises:
            Exception: If request fails
        """
        url = f"{self.BASE_URL}/{endpoint}"

        headers = {
            'Authorization': f'Bearer {self.bearer_token}',
            'User-Agent': 'CaseManager-OSINT/1.0'
        }

        try:
            if method == 'GET':
                response = requests.get(
                    url,
                    params=params or {},
                    headers=headers,
                    timeout=self.timeout
                )
            else:
                response = requests.request(
                    method,
                    url,
                    json=params or {},
                    headers=headers,
                    timeout=self.timeout
                )

            # Check for HTTP errors
            response.raise_for_status()

            data = response.json()

            # Check for API-specific errors
            if 'errors' in data:
                error_messages = [e.get('message', 'Unknown error') for e in data['errors']]
                logger.error(f"X API errors: {', '.join(error_messages)}")
                raise Exception(f"API Error: {', '.join(error_messages)}")

            return data

        except requests.exceptions.Timeout:
            logger.error(f"Timeout connecting to X API")
            raise Exception("Request timeout - the API took too long to respond")
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error to X API")
            raise Exception("Connection error - could not reach the API")
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error from X API: {e}")
            if response.status_code == 401:
                raise Exception("Invalid bearer token")
            elif response.status_code == 403:
                raise Exception("Bearer token does not have permission for this action")
            elif response.status_code == 429:
                # Extract rate limit info from headers
                reset_time = response.headers.get('x-rate-limit-reset')
                remaining = response.headers.get('x-rate-limit-remaining', '0')
                limit = response.headers.get('x-rate-limit-limit')

                error_msg = "Rate limit exceeded."
                if reset_time:
                    import datetime
                    reset_timestamp = int(reset_time)
                    reset_datetime = datetime.datetime.fromtimestamp(reset_timestamp)
                    now = datetime.datetime.now()
                    minutes_until_reset = max(0, int((reset_datetime - now).total_seconds() / 60))

                    if minutes_until_reset > 0:
                        error_msg += f" Podrás volver a intentar en {minutes_until_reset} minuto(s)."
                    else:
                        error_msg += " Puedes volver a intentar ahora."

                if limit:
                    error_msg += f" Límite: {remaining}/{limit} peticiones."

                raise Exception(error_msg)
            elif response.status_code == 404:
                raise Exception("User not found")
            else:
                raise Exception(f"HTTP error {response.status_code}")
        except Exception as e:
            logger.error(f"Unexpected error calling X API: {str(e)}")
            raise

    def get_user_by_username(self, username: str, include_metrics: bool = True) -> Dict[str, Any]:
        """
        Get user profile information by username.

        Args:
            username: Twitter username (without @)
            include_metrics: Include public metrics (followers, following, etc.)

        Returns:
            dict: User profile information containing:
                - id: User ID
                - name: Display name
                - username: Twitter handle
                - created_at: Account creation date
                - description: Bio
                - location: Location string
                - url: Profile URL
                - verified: Verification status
                - profile_image_url: Profile picture URL
                - public_metrics: Follower counts, tweet counts, etc.
                - protected: Is account private

        Raises:
            Exception: If lookup fails
        """
        # Clean username (remove @ if present)
        username = username.lstrip('@')

        # Build parameters
        params = {
            'user.fields': 'id,name,username,created_at,description,location,url,verified,profile_image_url,protected,public_metrics'
        }

        if not include_metrics:
            params['user.fields'] = 'id,name,username,created_at,description,location,url,verified,profile_image_url,protected'

        try:
            result = self._make_request(f"{self.USERS_BY_USERNAME}/{username}", params)

            # Track usage
            self.api_key_model.increment_usage()

            # Extract user data
            if 'data' not in result:
                raise Exception("No user data returned from API")

            user_data = result['data']

            # Add interpretation
            user_data['interpretation'] = self._interpret_user_profile(user_data)

            return {
                'success': True,
                'query': username,
                'query_type': 'username',
                'user': user_data
            }

        except Exception as e:
            logger.error(f"Error looking up user {username}: {str(e)}")
            raise

    def get_user_tweets(self, username: str = None, user_id: str = None,
                       max_results: int = 10, include_metrics: bool = True) -> Dict[str, Any]:
        """
        Get recent tweets from a user.

        Args:
            username: Twitter username (one of username or user_id required)
            user_id: Twitter user ID (one of username or user_id required)
            max_results: Number of tweets to retrieve (5-100, default 10)
            include_metrics: Include tweet metrics (likes, retweets, etc.)

        Returns:
            dict: Tweets and user information containing:
                - user: User profile data
                - tweets: List of recent tweets with:
                    - id: Tweet ID
                    - text: Tweet content
                    - created_at: Publication date
                    - public_metrics: Like, retweet, reply counts
                    - referenced_tweets: Quote tweets, replies, retweets
                    - entities: URLs, mentions, hashtags
                - meta: Pagination metadata

        Raises:
            Exception: If lookup fails
        """
        # Validate input
        if not username and not user_id:
            raise ValueError("Either username or user_id must be provided")

        # If username provided, get user_id first
        if username and not user_id:
            user_info = self.get_user_by_username(username, include_metrics=False)
            user_id = user_info['user']['id']
            user_data = user_info['user']
        else:
            # Get user info by ID
            user_data = self._get_user_by_id(user_id)

        # Validate max_results
        max_results = max(5, min(100, max_results))

        # Build parameters
        params = {
            'max_results': max_results,
            'tweet.fields': 'id,text,created_at,author_id,public_metrics,referenced_tweets,entities,lang'
        }

        if not include_metrics:
            params['tweet.fields'] = 'id,text,created_at,author_id,referenced_tweets,entities,lang'

        try:
            endpoint = self.USER_TWEETS_ENDPOINT.format(user_id)
            result = self._make_request(endpoint, params)

            # Track usage
            self.api_key_model.increment_usage()

            tweets = result.get('data', [])
            meta = result.get('meta', {})

            # Add interpretation to tweets
            for tweet in tweets:
                tweet['interpretation'] = self._interpret_tweet(tweet)

            return {
                'success': True,
                'query': username or user_id,
                'query_type': 'tweets',
                'user': user_data,
                'tweets': tweets,
                'meta': meta,
                'tweet_count': len(tweets)
            }

        except Exception as e:
            logger.error(f"Error getting tweets for user {username or user_id}: {str(e)}")
            raise

    def _get_user_by_id(self, user_id: str) -> Dict[str, Any]:
        """
        Get user profile by user ID.

        Args:
            user_id: Twitter user ID

        Returns:
            dict: User profile data
        """
        params = {
            'user.fields': 'id,name,username,created_at,description,location,url,verified,profile_image_url,protected,public_metrics'
        }

        result = self._make_request(f"{self.USERS_BY_ID}/{user_id}", params)

        if 'data' not in result:
            raise Exception("No user data returned from API")

        return result['data']

    def extract_username_from_url(self, url: str) -> Optional[str]:
        """
        Extract Twitter username from various URL formats.

        Args:
            url: Twitter profile URL or username

        Returns:
            str: Extracted username or None
        """
        # Remove @ if present
        if url.startswith('@'):
            return url[1:]

        # Try to extract from URL
        patterns = [
            r'(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/([a-zA-Z0-9_]+)',
            r'(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/@([a-zA-Z0-9_]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        # If no match, assume it's already a username
        if re.match(r'^[a-zA-Z0-9_]+$', url):
            return url

        return None

    def test_connection(self) -> Dict[str, Any]:
        """
        Test the API connection with a simple lookup.

        Returns:
            dict: Test result with success flag and details
        """
        try:
            # Test with a known account (Twitter's official account)
            result = self.get_user_by_username('Twitter', include_metrics=False)

            return {
                'success': True,
                'message': 'Connection successful',
                'details': {
                    'test_user': result['user']['username'],
                    'user_found': True
                }
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def _safe_int(self, value: Any, default: int = 0) -> int:
        """
        Safely convert a value to int.

        Args:
            value: Value to convert
            default: Default value if conversion fails

        Returns:
            int: Converted value or default
        """
        try:
            if isinstance(value, (int, float)):
                return int(value)
            elif isinstance(value, str):
                return int(float(value))
            return default
        except (ValueError, TypeError):
            return default

    def _interpret_user_profile(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Interpret user profile data and provide analysis.

        Args:
            user_data: Raw user data from API

        Returns:
            dict: Interpretation with profile analysis
        """
        metrics = user_data.get('public_metrics', {})
        followers = self._safe_int(metrics.get('followers_count', 0))
        following = self._safe_int(metrics.get('following_count', 0))
        tweets = self._safe_int(metrics.get('tweet_count', 0))

        # Calculate follower ratio
        follower_ratio = followers / max(following, 1)

        # Determine account type
        if user_data.get('verified', False):
            account_type = 'verified'
            credibility = 'high'
        elif followers > 10000:
            account_type = 'influencer'
            credibility = 'medium-high'
        elif follower_ratio > 2 and followers > 100:
            account_type = 'popular'
            credibility = 'medium'
        elif tweets < 10 and followers < 10:
            account_type = 'new_or_inactive'
            credibility = 'low'
        else:
            account_type = 'regular'
            credibility = 'medium'

        return {
            'account_type': account_type,
            'credibility': credibility,
            'follower_ratio': round(follower_ratio, 2),
            'activity_level': 'high' if tweets > 1000 else 'medium' if tweets > 100 else 'low',
            'protected': user_data.get('protected', False)
        }

    def _interpret_tweet(self, tweet_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Interpret tweet data and provide analysis.

        Args:
            tweet_data: Raw tweet data from API

        Returns:
            dict: Interpretation with tweet analysis
        """
        metrics = tweet_data.get('public_metrics', {})
        likes = self._safe_int(metrics.get('like_count', 0))
        retweets = self._safe_int(metrics.get('retweet_count', 0))
        replies = self._safe_int(metrics.get('reply_count', 0))

        # Calculate engagement
        total_engagement = likes + retweets + replies

        # Determine engagement level
        if total_engagement > 1000:
            engagement_level = 'viral'
        elif total_engagement > 100:
            engagement_level = 'high'
        elif total_engagement > 10:
            engagement_level = 'medium'
        else:
            engagement_level = 'low'

        # Check for referenced tweets
        ref_tweets = tweet_data.get('referenced_tweets', [])
        is_retweet = any(ref.get('type') == 'retweeted' for ref in ref_tweets)
        is_reply = any(ref.get('type') == 'replied_to' for ref in ref_tweets)
        is_quote = any(ref.get('type') == 'quoted' for ref in ref_tweets)

        return {
            'engagement_level': engagement_level,
            'total_engagement': total_engagement,
            'is_retweet': is_retweet,
            'is_reply': is_reply,
            'is_quote': is_quote,
            'language': tweet_data.get('lang', 'unknown')
        }
