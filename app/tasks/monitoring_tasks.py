"""
Celery tasks for monitoring operations.

Provides asynchronous task execution for:
- Periodic monitoring checks
- Single task execution
- AI analysis of results
- Media download
"""
import logging
from datetime import datetime
from celery import shared_task, current_task
from celery.exceptions import SoftTimeLimitExceeded

logger = logging.getLogger(__name__)


@shared_task(
    name='app.tasks.monitoring.check_all_active',
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    soft_time_limit=300,  # 5 minutes
    time_limit=360
)
def check_all_active_tasks(self):
    """
    Periodic task to check all active monitoring tasks.

    Runs every minute via Celery Beat, but only processes
    tasks that are due for their next check.

    This task delegates actual work to execute_single_check
    for each due task.
    """
    from app import create_app
    from app.services.monitoring_service import MonitoringService

    app = create_app()

    with app.app_context():
        try:
            # Get all tasks due for check
            due_tasks = MonitoringService.get_active_tasks()

            if not due_tasks:
                logger.debug("No monitoring tasks due for check")
                return {
                    'status': 'completed',
                    'tasks_found': 0,
                    'tasks_processed': 0
                }

            logger.info(f"Found {len(due_tasks)} monitoring tasks due for check")

            tasks_processed = 0
            errors = []

            for task in due_tasks:
                try:
                    # Execute check asynchronously
                    execute_single_check.delay(
                        task.id,
                        triggered_by='scheduled',
                        celery_task_id=self.request.id
                    )
                    tasks_processed += 1

                except Exception as e:
                    error_msg = f"Error queueing task {task.id}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            return {
                'status': 'completed',
                'tasks_found': len(due_tasks),
                'tasks_processed': tasks_processed,
                'errors': errors if errors else None
            }

        except SoftTimeLimitExceeded:
            logger.warning("check_all_active_tasks soft time limit exceeded")
            return {'status': 'timeout'}

        except Exception as e:
            logger.error(f"Error in check_all_active_tasks: {e}", exc_info=True)
            raise


@shared_task(
    name='app.tasks.monitoring.execute_single_check',
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
    soft_time_limit=600,  # 10 minutes
    time_limit=660
)
def execute_single_check(
    self,
    task_id: int,
    triggered_by: str = 'scheduled',
    user_id: int = None,
    celery_task_id: str = None
):
    """
    Execute monitoring check for a single task.

    Called by scheduler or manual trigger.

    Args:
        task_id: Monitoring task ID
        triggered_by: How the check was triggered ('scheduled' or 'manual')
        user_id: User ID if manually triggered
        celery_task_id: Parent Celery task ID if applicable
    """
    from app import create_app
    from app.services.monitoring_service import MonitoringService

    app = create_app()

    with app.app_context():
        try:
            logger.info(f"Executing monitoring check for task {task_id}")

            # Use current task ID if not provided
            if not celery_task_id:
                celery_task_id = self.request.id

            # Execute the check
            check_log = MonitoringService.execute_check(
                task_id=task_id,
                triggered_by=triggered_by,
                user_id=user_id,
                celery_task_id=celery_task_id
            )

            result = {
                'status': 'completed' if check_log.success else 'failed',
                'task_id': task_id,
                'check_log_id': check_log.id,
                'sources_checked': check_log.sources_checked,
                'new_results': check_log.new_results_count,
                'alerts_generated': check_log.alerts_generated,
                'errors': check_log.errors_count,
                'duration': check_log.duration_seconds
            }

            if not check_log.success:
                result['error'] = check_log.error_message

            logger.info(
                f"Monitoring check completed for task {task_id}: "
                f"{check_log.new_results_count} new results, "
                f"{check_log.alerts_generated} alerts"
            )

            return result

        except SoftTimeLimitExceeded:
            logger.warning(f"execute_single_check soft time limit exceeded for task {task_id}")
            return {
                'status': 'timeout',
                'task_id': task_id
            }

        except Exception as e:
            logger.error(f"Error executing check for task {task_id}: {e}", exc_info=True)
            raise


@shared_task(
    name='app.tasks.monitoring.analyze_result_with_ai',
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
    soft_time_limit=120,  # 2 minutes
    time_limit=150
)
def analyze_result_with_ai(self, result_id: int):
    """
    Run AI analysis on a monitoring result.

    Downloads media if needed, then calls AI service.

    Args:
        result_id: Monitoring result ID to analyze
    """
    from app import create_app
    from app.services.monitoring_service import MonitoringService
    from app.models.monitoring import MonitoringResult

    app = create_app()

    with app.app_context():
        try:
            result = MonitoringResult.query.get(result_id)
            if not result:
                logger.warning(f"Result {result_id} not found")
                return {'status': 'not_found', 'result_id': result_id}

            task = result.task
            if not task:
                logger.warning(f"Task not found for result {result_id}")
                return {'status': 'task_not_found', 'result_id': result_id}

            logger.info(f"Running AI analysis on result {result_id}")

            success = MonitoringService.analyze_result(result, task)

            return {
                'status': 'completed' if success else 'failed',
                'result_id': result_id,
                'is_alert': result.is_alert,
                'relevance_score': result.ai_relevance_score,
                'error': result.ai_error if not success else None
            }

        except SoftTimeLimitExceeded:
            logger.warning(f"analyze_result_with_ai soft time limit exceeded for result {result_id}")
            return {'status': 'timeout', 'result_id': result_id}

        except Exception as e:
            logger.error(f"Error analyzing result {result_id}: {e}", exc_info=True)
            raise


@shared_task(
    name='app.tasks.monitoring.download_result_media',
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
    soft_time_limit=180,  # 3 minutes
    time_limit=210
)
def download_result_media(self, result_id: int):
    """
    Download media files for a monitoring result.

    Args:
        result_id: Monitoring result ID
    """
    from app import create_app
    from app.extensions import db
    from app.models.monitoring import MonitoringResult
    from app.services.media_download_service import MediaDownloadService

    app = create_app()

    with app.app_context():
        try:
            result = MonitoringResult.query.get(result_id)
            if not result:
                logger.warning(f"Result {result_id} not found")
                return {'status': 'not_found', 'result_id': result_id}

            if result.media_downloaded:
                logger.info(f"Media already downloaded for result {result_id}")
                return {'status': 'already_downloaded', 'result_id': result_id}

            if not result.media_urls:
                logger.info(f"No media URLs for result {result_id}")
                return {'status': 'no_media', 'result_id': result_id}

            logger.info(f"Downloading media for result {result_id}")

            download_service = MediaDownloadService()
            downloaded = download_service.download_media(
                result.media_urls,
                result.task_id,
                result.id
            )

            # Store download results
            local_paths = []
            hashes = []
            errors = []

            for item in downloaded:
                if item['success']:
                    local_paths.append(item['local_path'])
                    hashes.append(item['sha256_hash'])
                else:
                    errors.append(item['error'])

            if local_paths:
                result.media_local_paths = local_paths
                result.media_hashes = hashes
                result.media_downloaded = True
                db.session.commit()

            return {
                'status': 'completed',
                'result_id': result_id,
                'files_downloaded': len(local_paths),
                'errors': errors if errors else None
            }

        except SoftTimeLimitExceeded:
            logger.warning(f"download_result_media soft time limit exceeded for result {result_id}")
            return {'status': 'timeout', 'result_id': result_id}

        except Exception as e:
            logger.error(f"Error downloading media for result {result_id}: {e}", exc_info=True)
            raise


@shared_task(
    name='app.tasks.monitoring.reanalyze_results',
    bind=True,
    soft_time_limit=1800,  # 30 minutes
    time_limit=1860
)
def reanalyze_results(self, task_id: int, force: bool = False):
    """
    Re-analyze all results for a monitoring task.

    Useful after changing the monitoring objective.

    Args:
        task_id: Monitoring task ID
        force: If True, re-analyze even already analyzed results
    """
    from app import create_app
    from app.services.monitoring_service import MonitoringService
    from app.models.monitoring import MonitoringTask, MonitoringResult

    app = create_app()

    with app.app_context():
        try:
            task = MonitoringTask.query.get(task_id)
            if not task:
                return {'status': 'not_found', 'task_id': task_id}

            # Get results to analyze
            query = task.results
            if not force:
                query = query.filter_by(ai_analyzed=False)

            results = query.all()
            logger.info(f"Re-analyzing {len(results)} results for task {task_id}")

            analyzed = 0
            errors = 0

            for result in results:
                try:
                    success = MonitoringService.analyze_result(result, task)
                    if success:
                        analyzed += 1
                    else:
                        errors += 1
                except Exception as e:
                    logger.error(f"Error analyzing result {result.id}: {e}")
                    errors += 1

            return {
                'status': 'completed',
                'task_id': task_id,
                'results_analyzed': analyzed,
                'errors': errors
            }

        except SoftTimeLimitExceeded:
            logger.warning(f"reanalyze_results soft time limit exceeded for task {task_id}")
            return {'status': 'timeout', 'task_id': task_id}

        except Exception as e:
            logger.error(f"Error re-analyzing results for task {task_id}: {e}", exc_info=True)
            raise
