"""
Apify API Service.

Service for interacting with Apify actors for OSINT data scraping.
Supports Instagram profile and posts scraping via the Instagram API Scraper actor.
"""
import requests
import logging
import time
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ApifyService:
    """
    Service for interacting with Apify API.

    This service provides methods to run Apify actors and retrieve results,
    specifically for Instagram data scraping via the Instagram API Scraper actor.
    """

    BASE_URL = 'https://api.apify.com/v2'
    INSTAGRAM_ACTOR_ID = 'RB9HEZitC8hIUXAha'

    def __init__(self, api_key_model):
        """
        Initialize Apify service with API key.

        Args:
            api_key_model: ApiKey model instance containing the Apify API token
        """
        self.api_key_model = api_key_model
        self.api_token = api_key_model.get_api_key()

    def run_actor(self, actor_id: str, run_input: Dict[str, Any],
                  wait_for_finish: bool = True, timeout: int = 120) -> Dict[str, Any]:
        """
        Run an Apify actor with given input.

        Args:
            actor_id: Apify actor ID (e.g., 'apify/instagram-api-scraper')
            run_input: Input parameters for the actor
            wait_for_finish: Whether to wait for the actor to finish
            timeout: Maximum time to wait in seconds (default 120s)

        Returns:
            dict: Actor run information including status and dataset ID

        Raises:
            Exception: If the actor run fails
        """
        url = f"{self.BASE_URL}/acts/{actor_id}/runs"
        params = {'token': self.api_token}

        # Start the actor
        response = requests.post(url, json=run_input, params=params, timeout=30)
        response.raise_for_status()
        run_info = response.json()['data']

        logger.info(f"Started Apify actor {actor_id}, run ID: {run_info['id']}")

        if not wait_for_finish:
            return run_info

        # Wait for completion with polling
        run_id = run_info['id']
        start_time = time.time()

        while time.time() - start_time < timeout:
            status_url = f"{self.BASE_URL}/acts/{actor_id}/runs/{run_id}"
            status_response = requests.get(status_url, params=params, timeout=10)
            status_response.raise_for_status()

            run_data = status_response.json()['data']
            status = run_data['status']

            if status == 'SUCCEEDED':
                logger.info(f"Actor run {run_id} succeeded")
                return run_data
            elif status in ['FAILED', 'TIMED-OUT', 'ABORTED']:
                error_msg = f"Actor run {run_id} {status.lower()}"
                logger.error(error_msg)
                raise Exception(error_msg)

            # Wait before next poll
            time.sleep(2)

        raise Exception(f"Actor run {run_id} timed out after {timeout} seconds")

    def get_dataset_items(self, dataset_id: str, limit: Optional[int] = None) -> list:
        """
        Retrieve items from an Apify dataset.

        Args:
            dataset_id: ID of the dataset to retrieve
            limit: Maximum number of items to retrieve (optional)

        Returns:
            list: List of dataset items
        """
        url = f"{self.BASE_URL}/datasets/{dataset_id}/items"
        params = {'token': self.api_token, 'format': 'json'}

        if limit:
            params['limit'] = limit

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        return response.json()

    def scrape_instagram_profile(self, username: str) -> Dict[str, Any]:
        """
        Scrape Instagram profile information.

        Args:
            username: Instagram username (without @)

        Returns:
            dict: Profile data including bio, followers, posts, etc.
        """
        # Prepare input for the actor
        run_input = {
            "directUrls": [f"https://www.instagram.com/{username}/"],
            "resultsType": "details",  # Get detailed profile info
            "resultsLimit": 1,
            "searchType": "user",
            "searchLimit": 1
        }

        try:
            # Run the actor
            run_data = self.run_actor(self.INSTAGRAM_ACTOR_ID, run_input)

            # Get results from dataset
            dataset_id = run_data['defaultDatasetId']
            items = self.get_dataset_items(dataset_id, limit=1)

            if not items:
                return {
                    'success': False,
                    'error': f'No se encontró el perfil @{username}',
                    'username': username
                }

            profile = items[0]

            return {
                'success': True,
                'query': username,
                'query_type': 'instagram_profile',
                'platform': 'Instagram',
                'data': self._format_profile_data(profile)
            }

        except Exception as e:
            logger.error(f"Error scraping Instagram profile @{username}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'username': username
            }

    def scrape_instagram_posts(self, username: str, max_posts: int = 12) -> Dict[str, Any]:
        """
        Scrape Instagram posts from a profile.

        Args:
            username: Instagram username (without @)
            max_posts: Maximum number of posts to retrieve (default 12)

        Returns:
            dict: Posts data with images, captions, likes, comments, etc.
        """
        # Prepare input for the actor
        run_input = {
            "directUrls": [f"https://www.instagram.com/{username}/"],
            "resultsType": "posts",  # Get posts
            "resultsLimit": max_posts,
            "searchType": "user"
        }

        try:
            # Run the actor
            run_data = self.run_actor(self.INSTAGRAM_ACTOR_ID, run_input)

            # Get results from dataset
            dataset_id = run_data['defaultDatasetId']
            items = self.get_dataset_items(dataset_id, limit=max_posts)

            if not items:
                return {
                    'success': False,
                    'error': f'No se encontraron posts para @{username}',
                    'username': username
                }

            # Separate profile data and posts
            profile_data = None
            posts = []

            for item in items:
                if item.get('type') == 'Profile':
                    profile_data = item
                elif item.get('type') in ['Image', 'Video', 'Sidecar']:
                    posts.append(item)

            return {
                'success': True,
                'query': username,
                'query_type': 'instagram_posts',
                'platform': 'Instagram',
                'profile': self._format_profile_data(profile_data) if profile_data else None,
                'posts': [self._format_post_data(post) for post in posts],
                'post_count': len(posts)
            }

        except Exception as e:
            logger.error(f"Error scraping Instagram posts @{username}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'username': username
            }

    def _format_profile_data(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """Format raw profile data into a structured format."""
        if not profile:
            return {}

        return {
            'id': profile.get('id'),
            'username': profile.get('username'),
            'full_name': profile.get('fullName'),
            'biography': profile.get('biography'),
            'external_url': profile.get('externalUrl'),
            'profile_pic_url': profile.get('profilePicUrl'),
            'is_private': profile.get('private', False),
            'is_verified': profile.get('verified', False),
            'is_business': profile.get('businessAccount', False),
            'followers_count': profile.get('followersCount', 0),
            'following_count': profile.get('followsCount', 0),
            'posts_count': profile.get('postsCount', 0),
            'category': profile.get('category'),
            'raw': profile
        }

    def _format_post_data(self, post: Dict[str, Any]) -> Dict[str, Any]:
        """Format raw post data into a structured format."""
        return {
            'id': post.get('id'),
            'shortcode': post.get('shortCode'),
            'type': post.get('type'),
            'url': post.get('url'),
            'caption': post.get('caption'),
            'hashtags': post.get('hashtags', []),
            'mentions': post.get('mentions', []),
            'likes_count': post.get('likesCount', 0),
            'comments_count': post.get('commentsCount', 0),
            'timestamp': post.get('timestamp'),
            'display_url': post.get('displayUrl'),
            'images': post.get('images', []),
            'videos': post.get('videoUrl', []) if isinstance(post.get('videoUrl'), list) else [post.get('videoUrl')] if post.get('videoUrl') else [],
            'dimensions': {
                'height': post.get('dimensions', {}).get('height'),
                'width': post.get('dimensions', {}).get('width')
            },
            'location': post.get('locationName'),
            'owner': {
                'id': post.get('ownerId'),
                'username': post.get('ownerUsername')
            },
            'child_posts': post.get('childPosts', []),
            'raw': post
        }
