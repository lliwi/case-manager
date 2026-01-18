"""
Monitoring Service for social media surveillance.

Coordinates all monitoring operations including:
- Creating and managing monitoring tasks
- Fetching data from social media sources
- Triggering AI analysis
- Managing monitoring results
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

from app.extensions import db
from app.models.monitoring import (
    MonitoringTask, MonitoringSource, MonitoringResult, MonitoringCheckLog,
    MonitoringStatus, SourcePlatform, SourceQueryType, AIProvider
)
from app.models.api_key import ApiKey
from app.services.ai_analysis_service import AIAnalysisService
from app.services.media_download_service import MediaDownloadService

logger = logging.getLogger(__name__)


class MonitoringService:
    """
    Business logic for monitoring operations.

    Handles:
    - CRUD operations for monitoring tasks and sources
    - Executing monitoring checks
    - Processing results and AI analysis
    - Converting results to evidence
    """

    # Default configuration
    DEFAULT_CHECK_INTERVAL = 60  # minutes
    DEFAULT_MAX_RESULTS = 20
    ALERT_THRESHOLD = 0.6  # AI relevance score threshold for alerts

    @staticmethod
    def create_task(
        case_id: int,
        name: str,
        monitoring_objective: str,
        user_id: int,
        start_date: datetime,
        description: Optional[str] = None,
        ai_provider: str = 'deepseek',
        ai_analysis_enabled: bool = True,
        check_interval_minutes: int = DEFAULT_CHECK_INTERVAL,
        end_date: Optional[datetime] = None,
        ai_prompt_template: Optional[str] = None
    ) -> MonitoringTask:
        """
        Create a new monitoring task.

        Args:
            case_id: Case ID to link the task to
            name: Task name
            monitoring_objective: The objective/question to detect
            user_id: User creating the task
            start_date: When monitoring should start
            description: Optional description
            ai_provider: AI provider ('openai' or 'deepseek')
            ai_analysis_enabled: Whether to enable AI analysis
            check_interval_minutes: How often to check (in minutes)
            end_date: Optional end date
            ai_prompt_template: Optional custom AI prompt

        Returns:
            Created MonitoringTask
        """
        task = MonitoringTask(
            case_id=case_id,
            name=name,
            description=description,
            monitoring_objective=monitoring_objective,
            ai_provider=AIProvider(ai_provider) if isinstance(ai_provider, str) else ai_provider,
            ai_analysis_enabled=ai_analysis_enabled,
            ai_prompt_template=ai_prompt_template,
            check_interval_minutes=check_interval_minutes,
            start_date=start_date,
            end_date=end_date,
            status=MonitoringStatus.DRAFT,
            created_by_id=user_id
        )

        db.session.add(task)
        db.session.commit()

        logger.info(f"Created monitoring task {task.id} for case {case_id}")
        return task

    @staticmethod
    def update_task(
        task_id: int,
        **kwargs
    ) -> Optional[MonitoringTask]:
        """
        Update a monitoring task.

        Args:
            task_id: Task ID to update
            **kwargs: Fields to update

        Returns:
            Updated task or None if not found
        """
        task = MonitoringTask.query.filter_by(
            id=task_id,
            is_deleted=False
        ).first()

        if not task:
            return None

        # Update allowed fields
        allowed_fields = {
            'name', 'description', 'monitoring_objective',
            'ai_provider', 'ai_analysis_enabled', 'ai_prompt_template',
            'check_interval_minutes', 'start_date', 'end_date'
        }

        for key, value in kwargs.items():
            if key in allowed_fields:
                if key == 'ai_provider' and isinstance(value, str):
                    value = AIProvider(value)
                setattr(task, key, value)

        task.updated_at = datetime.utcnow()
        db.session.commit()

        return task

    @staticmethod
    def add_source(
        task_id: int,
        platform: str,
        query_type: str,
        query_value: str,
        max_results_per_check: int = DEFAULT_MAX_RESULTS,
        include_media: bool = True
    ) -> Optional[MonitoringSource]:
        """
        Add a monitoring source to a task.

        Args:
            task_id: Task ID
            platform: Platform ('X_TWITTER' or 'INSTAGRAM')
            query_type: Query type ('USER_PROFILE', 'HASHTAG', 'SEARCH_QUERY')
            query_value: The value to search for
            max_results_per_check: Max results per check
            include_media: Whether to download media

        Returns:
            Created MonitoringSource
        """
        task = MonitoringTask.query.filter_by(
            id=task_id,
            is_deleted=False
        ).first()

        if not task:
            return None

        source = MonitoringSource(
            task_id=task_id,
            platform=SourcePlatform[platform] if isinstance(platform, str) else platform,
            query_type=SourceQueryType[query_type] if isinstance(query_type, str) else query_type,
            query_value=query_value,
            max_results_per_check=max_results_per_check,
            include_media=include_media
        )

        db.session.add(source)
        db.session.commit()

        logger.info(f"Added source {source.id} to task {task_id}: {platform} - {query_value}")
        return source

    @staticmethod
    def toggle_task_status(task_id: int, user_id: int) -> Tuple[bool, str]:
        """
        Toggle task status between active and paused.

        Args:
            task_id: Task ID
            user_id: User performing the action

        Returns:
            Tuple of (success, message)
        """
        task = MonitoringTask.query.filter_by(
            id=task_id,
            is_deleted=False
        ).first()

        if not task:
            return False, "Tarea no encontrada"

        # Check if task has sources
        if task.sources.count() == 0:
            return False, "La tarea debe tener al menos una fuente de datos"

        if task.status == MonitoringStatus.ACTIVE:
            task.pause()
            message = "Tarea pausada"
        elif task.status in (MonitoringStatus.DRAFT, MonitoringStatus.PAUSED):
            task.activate()
            message = "Tarea activada"
        else:
            return False, f"No se puede cambiar el estado desde {task.status.value}"

        db.session.commit()
        return True, message

    @staticmethod
    def get_active_tasks() -> List[MonitoringTask]:
        """
        Get all tasks that are due for a check.

        Returns:
            List of tasks ready for monitoring
        """
        now = datetime.utcnow()

        tasks = MonitoringTask.query.filter(
            MonitoringTask.status == MonitoringStatus.ACTIVE,
            MonitoringTask.is_deleted == False,
            MonitoringTask.next_check_at <= now
        ).all()

        return tasks

    @staticmethod
    def execute_check(
        task_id: int,
        triggered_by: str = 'scheduled',
        user_id: Optional[int] = None,
        celery_task_id: Optional[str] = None
    ) -> MonitoringCheckLog:
        """
        Execute a monitoring check for a task.

        Args:
            task_id: Task ID
            triggered_by: How the check was triggered ('scheduled' or 'manual')
            user_id: User ID if manually triggered
            celery_task_id: Celery task ID if applicable

        Returns:
            MonitoringCheckLog with results
        """
        # Create check log
        check_log = MonitoringCheckLog(
            task_id=task_id,
            check_started_at=datetime.utcnow(),
            triggered_by=triggered_by,
            triggered_by_user_id=user_id,
            celery_task_id=celery_task_id,
            sources_checked=0,
            new_results_count=0,
            ai_analyses_count=0,
            alerts_generated=0,
            errors_count=0,
            success=False
        )
        db.session.add(check_log)

        task = MonitoringTask.query.filter_by(
            id=task_id,
            is_deleted=False
        ).first()

        if not task:
            check_log.complete(success=False, error_message="Tarea no encontrada")
            db.session.commit()
            return check_log

        try:
            # Process each active source
            for source in task.sources.filter_by(is_active=True):
                try:
                    results = MonitoringService.process_source(source, task)
                    check_log.sources_checked += 1
                    check_log.new_results_count += len(results)

                    # Run AI analysis on new results
                    if task.ai_analysis_enabled and results:
                        for result in results:
                            try:
                                analysis_success = MonitoringService.analyze_result(result, task)
                                if analysis_success:
                                    check_log.ai_analyses_count += 1
                                    if result.is_alert:
                                        check_log.alerts_generated += 1
                            except Exception as e:
                                logger.error(f"Error analyzing result {result.id}: {e}")
                                check_log.errors_count += 1

                except Exception as e:
                    logger.error(f"Error processing source {source.id}: {e}")
                    source.record_error(str(e))
                    check_log.errors_count += 1

            # Update task statistics
            task.total_checks += 1
            task.total_results += check_log.new_results_count
            task.last_check_at = datetime.utcnow()
            task.calculate_next_check()

            check_log.complete(success=True)

        except Exception as e:
            logger.error(f"Error executing check for task {task_id}: {e}", exc_info=True)
            check_log.complete(success=False, error_message=str(e))

        db.session.commit()
        return check_log

    @staticmethod
    def process_source(source: MonitoringSource, task: MonitoringTask) -> List[MonitoringResult]:
        """
        Fetch new content from a single source.

        Args:
            source: The source to process
            task: Parent monitoring task

        Returns:
            List of new MonitoringResult objects
        """
        results = []

        if source.platform == SourcePlatform.X_TWITTER:
            results = MonitoringService._process_x_source(source, task)
        elif source.platform == SourcePlatform.INSTAGRAM:
            results = MonitoringService._process_instagram_source(source, task)

        # Update source state
        source.last_check_at = datetime.utcnow()
        if results:
            source.clear_errors()

        return results

    @staticmethod
    def _process_x_source(source: MonitoringSource, task: MonitoringTask) -> List[MonitoringResult]:
        """Process X (Twitter) source."""
        from app.services.x_api_service import XAPIService

        results = []

        # Get API key
        api_key = ApiKey.get_active_key('x_api')
        if not api_key:
            source.record_error("No hay API Key activa para X API")
            return results

        service = XAPIService(api_key)

        try:
            if source.query_type == SourceQueryType.USER_PROFILE:
                # Get user tweets
                username = source.query_value.lstrip('@')
                tweets_data = service.get_user_tweets(
                    username,
                    max_results=source.max_results_per_check,
                    since_id=source.last_result_id
                )

                if tweets_data and tweets_data.get('tweets'):
                    for tweet in tweets_data['tweets']:
                        # Check if we already have this result
                        existing = MonitoringResult.query.filter_by(
                            task_id=task.id,
                            source_id=source.id,
                            external_id=tweet['id']
                        ).first()

                        if existing:
                            continue

                        # Create result
                        result = MonitoringService._create_result_from_tweet(
                            tweet, source, task, tweets_data.get('user', {})
                        )
                        results.append(result)

                    # Update last result ID
                    if tweets_data['tweets']:
                        source.last_result_id = tweets_data['tweets'][0]['id']

            elif source.query_type == SourceQueryType.HASHTAG:
                # Search for hashtag
                hashtag = source.query_value.lstrip('#')
                query = f"#{hashtag}"

                tweets_data = service.search_tweets(
                    query,
                    max_results=source.max_results_per_check,
                    since_id=source.last_result_id
                )

                if tweets_data and tweets_data.get('tweets'):
                    for tweet in tweets_data['tweets']:
                        # Check if we already have this result
                        existing = MonitoringResult.query.filter_by(
                            task_id=task.id,
                            source_id=source.id,
                            external_id=tweet['id']
                        ).first()

                        if existing:
                            continue

                        # Create result from tweet
                        result = MonitoringService._create_result_from_search_tweet(
                            tweet, source, task
                        )
                        results.append(result)

                    # Update last result ID
                    if tweets_data['tweets']:
                        source.last_result_id = tweets_data['tweets'][0]['id']

            elif source.query_type == SourceQueryType.SEARCH_QUERY:
                # Search query
                tweets_data = service.search_tweets(
                    source.query_value,
                    max_results=source.max_results_per_check,
                    since_id=source.last_result_id
                )

                if tweets_data and tweets_data.get('tweets'):
                    for tweet in tweets_data['tweets']:
                        # Check if we already have this result
                        existing = MonitoringResult.query.filter_by(
                            task_id=task.id,
                            source_id=source.id,
                            external_id=tweet['id']
                        ).first()

                        if existing:
                            continue

                        # Create result from tweet
                        result = MonitoringService._create_result_from_search_tweet(
                            tweet, source, task
                        )
                        results.append(result)

                    # Update last result ID
                    if tweets_data['tweets']:
                        source.last_result_id = tweets_data['tweets'][0]['id']

        except Exception as e:
            source.record_error(str(e))
            logger.error(f"Error processing X source {source.id}: {e}")

        return results

    @staticmethod
    def _process_instagram_source(source: MonitoringSource, task: MonitoringTask) -> List[MonitoringResult]:
        """Process Instagram source."""
        from app.services.apify_service import ApifyService

        results = []

        # Get API key
        api_key = ApiKey.get_active_key('apify')
        if not api_key:
            source.record_error("No hay API Key activa para Apify")
            return results

        service = ApifyService(api_key)

        try:
            if source.query_type == SourceQueryType.USER_PROFILE:
                # Get user posts
                username = source.query_value.lstrip('@')
                posts_data = service.scrape_instagram_posts(
                    username,
                    max_posts=source.max_results_per_check
                )

                if not posts_data:
                    source.record_error('No se recibió respuesta del servicio de Instagram')
                    return results

                if not posts_data.get('success'):
                    source.record_error(posts_data.get('error', 'Error desconocido'))
                    return results

                if posts_data.get('posts'):
                    # Track if we found the last processed post
                    found_last_post = False
                    new_posts_found = False

                    for post in posts_data['posts']:
                        post_id = post.get('id') or post.get('shortCode')
                        if not post_id:
                            continue

                        # If we have a last_result_id, skip posts we've already seen
                        if source.last_result_id and str(post_id) == str(source.last_result_id):
                            found_last_post = True
                            break  # Stop processing older posts

                        # Check if we already have this result in database
                        existing = MonitoringResult.query.filter_by(
                            task_id=task.id,
                            source_id=source.id,
                            external_id=str(post_id)
                        ).first()

                        if existing:
                            continue

                        # Create result
                        result = MonitoringService._create_result_from_instagram_post(
                            post, source, task, posts_data.get('profile', {})
                        )
                        results.append(result)
                        new_posts_found = True

                    # Update last result ID only if we found new posts
                    if new_posts_found and posts_data['posts']:
                        first_post = posts_data['posts'][0]
                        source.last_result_id = first_post.get('id') or first_post.get('shortCode')

            elif source.query_type == SourceQueryType.HASHTAG:
                # Hashtag monitoring would need different Apify actor
                logger.warning("Hashtag search not yet fully implemented for Instagram")

        except Exception as e:
            source.record_error(str(e))
            logger.error(f"Error processing Instagram source {source.id}: {e}")

        return results

    @staticmethod
    def _create_result_from_tweet(
        tweet: Dict,
        source: MonitoringSource,
        task: MonitoringTask,
        user_data: Dict
    ) -> MonitoringResult:
        """Create a MonitoringResult from X tweet data."""
        from dateutil import parser as date_parser

        # Extract media URLs
        media_urls = []
        if tweet.get('attachments', {}).get('media'):
            for media in tweet['attachments']['media']:
                if media.get('url'):
                    media_urls.append(media['url'])
                elif media.get('preview_image_url'):
                    media_urls.append(media['preview_image_url'])

        # Parse timestamp
        source_timestamp = None
        if tweet.get('created_at'):
            try:
                source_timestamp = date_parser.parse(tweet['created_at'])
            except Exception:
                pass

        # Build external URL
        username = user_data.get('username', '')
        external_url = f"https://x.com/{username}/status/{tweet['id']}" if username else None

        # Calculate content hash
        content_hash = MonitoringResult.calculate_content_hash(
            tweet.get('text', ''),
            tweet['id'],
            source_timestamp
        )

        result = MonitoringResult(
            task_id=task.id,
            source_id=source.id,
            external_id=tweet['id'],
            external_url=external_url,
            content_text=tweet.get('text', ''),
            content_metadata=tweet,
            author_username=username,
            author_display_name=user_data.get('name', ''),
            author_profile_url=f"https://x.com/{username}" if username else None,
            has_media=len(media_urls) > 0,
            media_count=len(media_urls),
            media_urls=media_urls if media_urls else None,
            source_timestamp=source_timestamp,
            content_hash=content_hash
        )

        db.session.add(result)
        db.session.flush()  # Get the ID

        # Download media if enabled
        if source.include_media and media_urls:
            MonitoringService._download_result_media(result, media_urls)

        return result

    @staticmethod
    def _create_result_from_search_tweet(
        tweet: Dict,
        source: MonitoringSource,
        task: MonitoringTask
    ) -> MonitoringResult:
        """Create a MonitoringResult from X search tweet data."""
        from dateutil import parser as date_parser

        # Get author info from embedded data
        author = tweet.get('author', {})
        username = author.get('username', '')

        # Extract media URLs
        media_urls = []
        if tweet.get('media'):
            for media in tweet['media']:
                if media.get('url'):
                    media_urls.append(media['url'])
                elif media.get('preview_image_url'):
                    media_urls.append(media['preview_image_url'])

        # Parse timestamp
        source_timestamp = None
        if tweet.get('created_at'):
            try:
                source_timestamp = date_parser.parse(tweet['created_at'])
            except Exception:
                pass

        # Build external URL
        external_url = f"https://x.com/{username}/status/{tweet['id']}" if username else None

        # Calculate content hash
        content_hash = MonitoringResult.calculate_content_hash(
            tweet.get('text', ''),
            tweet['id'],
            source_timestamp
        )

        result = MonitoringResult(
            task_id=task.id,
            source_id=source.id,
            external_id=tweet['id'],
            external_url=external_url,
            content_text=tweet.get('text', ''),
            content_metadata=tweet,
            author_username=username,
            author_display_name=author.get('name', ''),
            author_profile_url=f"https://x.com/{username}" if username else None,
            has_media=len(media_urls) > 0,
            media_count=len(media_urls),
            media_urls=media_urls if media_urls else None,
            source_timestamp=source_timestamp,
            content_hash=content_hash
        )

        db.session.add(result)
        db.session.flush()  # Get the ID

        # Download media if enabled
        if source.include_media and media_urls:
            MonitoringService._download_result_media(result, media_urls)

        return result

    @staticmethod
    def _create_result_from_instagram_post(
        post: Dict,
        source: MonitoringSource,
        task: MonitoringTask,
        profile_data: Dict
    ) -> MonitoringResult:
        """Create a MonitoringResult from Instagram post data."""
        from dateutil import parser as date_parser

        post_id = post.get('id') or post.get('shortCode')

        # Extract media URLs
        media_urls = []
        if post.get('displayUrl'):
            media_urls.append(post['displayUrl'])
        if post.get('images'):
            media_urls.extend(post['images'])
        if post.get('videoUrl'):
            media_urls.append(post['videoUrl'])

        # Parse timestamp
        source_timestamp = None
        if post.get('timestamp'):
            try:
                source_timestamp = date_parser.parse(post['timestamp'])
            except Exception:
                pass

        # Build external URL
        shortcode = post.get('shortCode', '')
        external_url = f"https://www.instagram.com/p/{shortcode}/" if shortcode else None

        # Get caption
        caption = post.get('caption', '') or ''

        # Calculate content hash
        content_hash = MonitoringResult.calculate_content_hash(
            caption,
            str(post_id),
            source_timestamp
        )

        # Handle None profile_data
        profile_data = profile_data or {}
        username = profile_data.get('username') or source.query_value.lstrip('@')

        result = MonitoringResult(
            task_id=task.id,
            source_id=source.id,
            external_id=str(post_id),
            external_url=external_url,
            content_text=caption,
            content_metadata=post,
            author_username=username,
            author_display_name=profile_data.get('fullName') or '',
            author_profile_url=f"https://www.instagram.com/{username}/" if username else None,
            has_media=len(media_urls) > 0,
            media_count=len(media_urls),
            media_urls=media_urls if media_urls else None,
            source_timestamp=source_timestamp,
            content_hash=content_hash
        )

        db.session.add(result)
        db.session.flush()

        # Download media if enabled
        if source.include_media and media_urls:
            MonitoringService._download_result_media(result, media_urls)

        return result

    @staticmethod
    def _download_result_media(result: MonitoringResult, media_urls: List[str]):
        """Download media for a result."""
        try:
            download_service = MediaDownloadService()
            downloaded = download_service.download_media(
                media_urls,
                result.task_id,
                result.id
            )

            # Store download results
            local_paths = []
            hashes = []

            for item in downloaded:
                if item['success']:
                    local_paths.append(item['local_path'])
                    hashes.append(item['sha256_hash'])

            if local_paths:
                result.media_local_paths = local_paths
                result.media_hashes = hashes
                result.media_downloaded = True

        except Exception as e:
            logger.error(f"Error downloading media for result {result.id}: {e}")

    @staticmethod
    def analyze_result(result: MonitoringResult, task: MonitoringTask) -> bool:
        """
        Run AI analysis on a monitoring result.

        Args:
            result: Result to analyze
            task: Parent monitoring task

        Returns:
            True if analysis was successful
        """
        try:
            # Initialize AI service
            ai_service = AIAnalysisService(
                provider=task.ai_provider.value if task.ai_provider else 'deepseek'
            )

            # Prepare images for analysis
            images = []
            if result.media_downloaded and result.media_local_paths:
                download_service = MediaDownloadService()
                images = download_service.get_media_for_analysis(result.media_local_paths)
            elif result.media_urls:
                # Use URLs directly if not downloaded
                images = result.media_urls[:4]  # Limit to 4 images

            # Build context
            context = {
                'case_name': task.case.numero_orden if task.case else 'Desconocido',
                'subject': result.author_username or 'Desconocido',
                'platform': result.source.platform.value if result.source else 'Desconocido'
            }

            # Run analysis
            analysis = ai_service.analyze_content(
                text=result.content_text,
                images=images,
                objective=task.monitoring_objective,
                context=context,
                custom_prompt=task.ai_prompt_template
            )

            # Store results
            result.ai_analyzed = True
            result.ai_analysis_timestamp = datetime.utcnow()
            result.ai_provider_used = analysis.get('provider')
            result.ai_model_used = analysis.get('model')
            result.ai_analysis_result = analysis

            if analysis.get('success'):
                result.ai_relevance_score = analysis.get('relevance_score', 0)
                result.ai_summary = analysis.get('summary', '')
                result.ai_flags = analysis.get('flags', [])

                # Check if should be marked as alert
                if analysis.get('is_alert') or (
                    result.ai_relevance_score and
                    result.ai_relevance_score >= MonitoringService.ALERT_THRESHOLD
                ):
                    result.mark_as_alert(
                        score=result.ai_relevance_score,
                        flags=result.ai_flags
                    )
            else:
                result.ai_error = analysis.get('error')

            db.session.commit()
            return True

        except Exception as e:
            logger.error(f"Error in AI analysis for result {result.id}: {e}", exc_info=True)
            result.ai_analyzed = True
            result.ai_analysis_timestamp = datetime.utcnow()
            result.ai_error = str(e)
            db.session.commit()
            return False

    @staticmethod
    def save_result_as_evidence(
        result_id: int,
        user_id: int,
        description: Optional[str] = None
    ) -> Optional[Any]:
        """
        Convert a monitoring result to case evidence.

        Args:
            result_id: Result ID
            user_id: User performing the action
            description: Optional description for evidence

        Returns:
            Created Evidence object or None if error
        """
        from app.models.evidence import Evidence, EvidenceType
        from app.services.evidence_service import EvidenceService
        import json

        result = MonitoringResult.query.get(result_id)
        if not result or result.saved_as_evidence:
            return None

        task = result.task
        if not task:
            return None

        try:
            # Create evidence metadata
            metadata = {
                'source': 'monitoring',
                'monitoring_task_id': task.id,
                'monitoring_result_id': result.id,
                'platform': result.source.platform.value if result.source else None,
                'external_url': result.external_url,
                'author_username': result.author_username,
                'source_timestamp': result.source_timestamp.isoformat() if result.source_timestamp else None,
                'ai_analysis': {
                    'relevance_score': result.ai_relevance_score,
                    'summary': result.ai_summary,
                    'flags': result.ai_flags
                } if result.ai_analyzed else None
            }

            # Determine evidence type
            if result.has_media:
                evidence_type = EvidenceType.IMAGEN_DIGITAL
            else:
                evidence_type = EvidenceType.OTRO

            # Build description
            if not description:
                platform_name = result.source.platform.value if result.source else 'Red social'
                description = f"Captura de {platform_name}"
                if result.author_username:
                    description += f" - Usuario: @{result.author_username}"
                if result.ai_summary:
                    description += f"\n\nAnálisis IA: {result.ai_summary}"

            # For now, create a text evidence with the content
            # In a full implementation, we would create proper evidence files

            evidence = Evidence(
                case_id=task.case_id,
                evidence_type=evidence_type,
                original_filename=f"monitoring_{result.external_id}.json",
                description=description,
                notes=json.dumps(metadata, ensure_ascii=False, indent=2),
                created_by_id=user_id,
                acquisition_method='monitoring_automatico',
                source_device=result.source.platform.value if result.source else None,
                source_location=result.external_url
            )

            db.session.add(evidence)
            db.session.flush()

            # Mark result as saved
            result.saved_as_evidence = True
            result.evidence_id = evidence.id

            db.session.commit()

            logger.info(f"Saved monitoring result {result_id} as evidence {evidence.id}")
            return evidence

        except Exception as e:
            logger.error(f"Error saving result as evidence: {e}", exc_info=True)
            db.session.rollback()
            return None

    @staticmethod
    def get_task_statistics(task_id: int) -> Dict[str, Any]:
        """
        Get aggregated statistics for a monitoring task.

        Args:
            task_id: Task ID

        Returns:
            Dict with statistics
        """
        task = MonitoringTask.query.get(task_id)
        if not task:
            return {}

        # Count results by alert status
        total_results = task.results.filter_by().count()
        alerts = task.results.filter_by(is_alert=True).count()
        acknowledged = task.results.filter_by(is_alert=True, alert_acknowledged=True).count()
        saved_as_evidence = task.results.filter_by(saved_as_evidence=True).count()

        # Get recent check logs
        recent_logs = task.check_logs.order_by(
            MonitoringCheckLog.check_started_at.desc()
        ).limit(10).all()

        # Calculate success rate
        if recent_logs:
            success_count = sum(1 for log in recent_logs if log.success)
            success_rate = success_count / len(recent_logs)
        else:
            success_rate = None

        # Get source statistics
        sources = []
        for source in task.sources.all():
            sources.append({
                'id': source.id,
                'platform': source.platform.value,
                'query_value': source.query_value,
                'is_active': source.is_active,
                'error_count': source.error_count,
                'results_count': source.results.count()
            })

        # Get media storage stats
        download_service = MediaDownloadService()
        storage_stats = download_service.get_storage_stats(task_id)

        return {
            'task_id': task_id,
            'status': task.status.value,
            'total_checks': task.total_checks,
            'total_results': total_results,
            'alerts_count': alerts,
            'alerts_pending': alerts - acknowledged,
            'alerts_acknowledged': acknowledged,
            'saved_as_evidence': saved_as_evidence,
            'sources_count': len(sources),
            'sources': sources,
            'success_rate': success_rate,
            'last_check_at': task.last_check_at.isoformat() if task.last_check_at else None,
            'next_check_at': task.next_check_at.isoformat() if task.next_check_at else None,
            'storage': storage_stats
        }

    @staticmethod
    def delete_task(task_id: int, user_id: int) -> bool:
        """
        Soft delete a monitoring task.

        Args:
            task_id: Task ID
            user_id: User performing the deletion

        Returns:
            True if successful
        """
        task = MonitoringTask.query.filter_by(
            id=task_id,
            is_deleted=False
        ).first()

        if not task:
            return False

        task.soft_delete(user_id)
        db.session.commit()

        logger.info(f"Deleted monitoring task {task_id}")
        return True
