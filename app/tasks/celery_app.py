"""
Celery application configuration.

This module initializes the Celery application for asynchronous task processing.
"""
import os
from celery import Celery
from celery.schedules import crontab


def make_celery():
    """
    Create and configure Celery application.

    Returns:
        Configured Celery instance
    """
    celery = Celery(
        'case_manager',
        broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
        backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1'),
        include=[
            'app.tasks.evidence_tasks',
            'app.tasks.forensic_tasks',
            'app.tasks.osint_tasks',
            'app.tasks.monitoring_tasks',
        ]
    )

    # Celery configuration
    celery.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='Europe/Madrid',
        enable_utc=True,
        task_track_started=True,
        task_time_limit=3600,  # 1 hour max per task
        task_soft_time_limit=3000,  # 50 minutes soft limit
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=1000,
        result_expires=3600,  # Results expire after 1 hour

        # Scheduled tasks
        beat_schedule={
            'cleanup-old-results': {
                'task': 'app.tasks.maintenance.cleanup_old_results',
                'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
            },
            'monitoring-check-active-tasks': {
                'task': 'app.tasks.monitoring.check_all_active',
                'schedule': crontab(minute='*'),  # Every minute
            },
        }
    )

    return celery


# Create Celery instance
celery = make_celery()


if __name__ == '__main__':
    celery.start()
