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
            # Run the actor with extended timeout for Instagram
            run_data = self.run_actor(self.INSTAGRAM_ACTOR_ID, run_input, timeout=300)

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
            # No limit enforced here - we get all posts returned by Apify
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

    def scrape_instagram_hashtag(self, hashtag: str, max_posts: int = 20) -> Dict[str, Any]:
        """
        Scrape Instagram posts by hashtag.

        Args:
            hashtag: Hashtag to search (without #)
            max_posts: Maximum number of posts to retrieve (default 20)

        Returns:
            dict: Posts data with images, captions, likes, comments, etc.
        """
        # Clean hashtag
        hashtag = hashtag.lstrip('#')

        # Prepare input for the actor
        run_input = {
            "directUrls": [f"https://www.instagram.com/explore/tags/{hashtag}/"],
            "resultsType": "posts",
            "resultsLimit": max_posts,
            "searchType": "hashtag"
        }

        try:
            # Run the actor with extended timeout
            run_data = self.run_actor(self.INSTAGRAM_ACTOR_ID, run_input, timeout=300)

            # Get results from dataset
            dataset_id = run_data['defaultDatasetId']
            items = self.get_dataset_items(dataset_id, limit=max_posts)

            if not items:
                return {
                    'success': False,
                    'error': f'No se encontraron posts para #{hashtag}',
                    'hashtag': hashtag
                }

            # Filter posts only - also accept items without 'type' if they have shortCode/id
            # No limit enforced here - we get all posts returned by Apify
            posts = []
            for item in items:
                item_type = item.get('type')
                has_id = item.get('id') or item.get('shortCode') or item.get('shortcode') or item.get('code')
                if item_type in ['Image', 'Video', 'Sidecar'] or (has_id and item_type is None):
                    posts.append(item)

            logger.info(f"Instagram hashtag #{hashtag}: found {len(items)} items, {len(posts)} valid posts")

            # Log first post raw data for debugging
            if posts:
                first_post = posts[0]
                logger.info(f"Instagram hashtag first post keys: {list(first_post.keys())}")
                logger.info(f"Instagram hashtag first post sample data: id={first_post.get('id')}, "
                           f"shortCode={first_post.get('shortCode')}, caption={str(first_post.get('caption', ''))[:100]}, "
                           f"displayUrl={first_post.get('displayUrl')}, ownerUsername={first_post.get('ownerUsername')}")

            formatted_posts = [self._format_post_data(post) for post in posts]

            return {
                'success': True,
                'query': hashtag,
                'query_type': 'instagram_hashtag',
                'platform': 'Instagram',
                'posts': formatted_posts,
                'post_count': len(formatted_posts)
            }

        except Exception as e:
            logger.error(f"Error scraping Instagram hashtag #{hashtag}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'hashtag': hashtag
            }

    def scrape_instagram_search(self, query: str, max_posts: int = 20) -> Dict[str, Any]:
        """
        Search Instagram posts by keyword/query.

        Args:
            query: Search query
            max_posts: Maximum number of posts to retrieve (default 20)

        Returns:
            dict: Posts data matching the search query
        """
        # Prepare input for the actor - search uses hashtag-like behavior
        run_input = {
            "search": query,
            "resultsType": "posts",
            "resultsLimit": max_posts,
            "searchType": "hashtag"  # Search uses hashtag search type
        }

        try:
            # Run the actor with extended timeout
            run_data = self.run_actor(self.INSTAGRAM_ACTOR_ID, run_input, timeout=300)

            # Get results from dataset
            dataset_id = run_data['defaultDatasetId']
            items = self.get_dataset_items(dataset_id, limit=max_posts)

            if not items:
                return {
                    'success': False,
                    'error': f'No se encontraron posts para "{query}"',
                    'query': query
                }

            # Filter posts only - also accept items without 'type' if they have shortCode/id
            # No limit enforced here - we get all posts returned by Apify
            posts = []
            for item in items:
                item_type = item.get('type')
                has_id = item.get('id') or item.get('shortCode') or item.get('shortcode') or item.get('code')
                if item_type in ['Image', 'Video', 'Sidecar'] or (has_id and item_type is None):
                    posts.append(item)

            logger.info(f"Instagram search '{query}': found {len(items)} items, {len(posts)} valid posts")

            formatted_posts = [self._format_post_data(post) for post in posts]

            return {
                'success': True,
                'query': query,
                'query_type': 'instagram_search',
                'platform': 'Instagram',
                'posts': formatted_posts,
                'post_count': len(formatted_posts)
            }

        except Exception as e:
            logger.error(f"Error searching Instagram for '{query}': {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'query': query
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
        # Handle different field names from Apify (camelCase vs snake_case, etc.)
        shortcode = post.get('shortCode') or post.get('shortcode') or post.get('code') or ''
        post_id = post.get('id') or shortcode

        # Get display URL (different field names depending on search type)
        display_url = (
            post.get('displayUrl') or
            post.get('display_url') or
            post.get('imageUrl') or
            post.get('image_url') or
            post.get('thumbnailUrl') or
            post.get('thumbnail_url') or
            post.get('previewUrl') or
            post.get('mediaUrl') or
            post.get('src') or
            post.get('image') or
            post.get('thumbnail_src') or
            ''
        )

        # Get owner info (can be nested or flat)
        owner_data = post.get('owner', {})
        owner_id = owner_data.get('id') or post.get('ownerId') or ''
        owner_username = owner_data.get('username') or post.get('ownerUsername') or ''

        # Get images list - try multiple field names
        images = (
            post.get('images') or
            post.get('displayResources') or
            post.get('display_resources') or
            post.get('sidecarImages') or
            []
        )

        # Handle display_resources structure (list of dicts with 'src')
        if images and isinstance(images, list) and len(images) > 0:
            if isinstance(images[0], dict):
                # Extract URLs from dict structure
                images = [img.get('src') or img.get('url') or img for img in images if img]
                images = [img for img in images if isinstance(img, str)]

        # Add display_url if not in images
        if display_url and display_url not in images:
            images = [display_url] + images

        # If still no images, try to build from shortcode
        if not images and not display_url:
            logger.debug(f"Instagram post {post_id} has no images. Available keys: {list(post.keys())}")

        # Get videos - try multiple field names
        video_url = (
            post.get('videoUrl') or
            post.get('video_url') or
            post.get('videoSrc') or
            post.get('video_src') or
            post.get('video')
        )
        videos = post.get('videos') or []
        if video_url and video_url not in videos:
            if isinstance(video_url, list):
                videos = video_url + videos
            else:
                videos = [video_url] + videos

        # Get caption - try multiple field names used by different Apify actors
        caption = (
            post.get('caption') or
            post.get('text') or
            post.get('description') or
            post.get('alt') or
            ''
        )
        # Handle nested caption structure (edge_media_to_caption)
        if not caption and post.get('edge_media_to_caption'):
            edges = post.get('edge_media_to_caption', {}).get('edges', [])
            if edges and edges[0].get('node', {}).get('text'):
                caption = edges[0]['node']['text']

        if not caption:
            logger.debug(f"Instagram post {post_id} has no caption. Available keys: {list(post.keys())}")

        return {
            'id': post_id,
            'shortcode': shortcode,
            'type': post.get('type', 'Image'),
            'url': post.get('url') or f"https://www.instagram.com/p/{shortcode}/" if shortcode else '',
            'caption': caption,
            'hashtags': post.get('hashtags', []),
            'mentions': post.get('mentions', []),
            'likes_count': post.get('likesCount') or post.get('likes_count') or 0,
            'comments_count': post.get('commentsCount') or post.get('comments_count') or 0,
            'timestamp': post.get('timestamp') or post.get('taken_at_timestamp'),
            'display_url': display_url,
            'images': images,
            'videos': videos,
            'dimensions': {
                'height': post.get('dimensions', {}).get('height'),
                'width': post.get('dimensions', {}).get('width')
            },
            'location': post.get('locationName') or post.get('location_name'),
            'owner': {
                'id': owner_id,
                'username': owner_username
            },
            'child_posts': post.get('childPosts', []) or post.get('sidecar_edges', []),
            'raw': post
        }
