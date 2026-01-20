"""
Task monitoring routes for Celery task management.
"""
from flask import render_template, jsonify, request
from flask_login import login_required, current_user
from app.blueprints.tasks import tasks_bp
from app.tasks.celery_app import celery
from app.utils.decorators import require_role, audit_action
from celery.result import AsyncResult
import json


@tasks_bp.route('/monitor')
@login_required
@require_role('admin')
@audit_action('TASKS_MONITOR_VIEWED', 'task')
def monitor():
    """Task monitoring dashboard."""
    return render_template('tasks/monitor.html')


@tasks_bp.route('/api/list')
@login_required
@require_role('admin')
def api_list_tasks():
    """List all active and recent tasks via API."""
    try:
        # Get active tasks from Celery
        inspector = celery.control.inspect()

        active_tasks = inspector.active() or {}
        scheduled_tasks = inspector.scheduled() or {}
        reserved_tasks = inspector.reserved() or {}

        # Combine all tasks
        all_tasks = []

        # Process active tasks
        for worker, tasks in active_tasks.items():
            for task in tasks:
                all_tasks.append({
                    'id': task['id'],
                    'name': task['name'],
                    'worker': worker,
                    'state': 'ACTIVE',
                    'args': task.get('args', []),
                    'kwargs': task.get('kwargs', {})
                })

        # Process scheduled tasks
        for worker, tasks in scheduled_tasks.items():
            for task in tasks:
                all_tasks.append({
                    'id': task['request']['id'],
                    'name': task['request']['name'],
                    'worker': worker,
                    'state': 'SCHEDULED',
                    'eta': task.get('eta'),
                    'args': task['request'].get('args', []),
                    'kwargs': task['request'].get('kwargs', {})
                })

        # Process reserved tasks
        for worker, tasks in reserved_tasks.items():
            for task in tasks:
                all_tasks.append({
                    'id': task['id'],
                    'name': task['name'],
                    'worker': worker,
                    'state': 'RESERVED',
                    'args': task.get('args', []),
                    'kwargs': task.get('kwargs', {})
                })

        return jsonify({
            'success': True,
            'tasks': all_tasks
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@tasks_bp.route('/api/status/<task_id>')
@login_required
@require_role('admin')
def api_task_status(task_id):
    """Get status of a specific task."""
    try:
        result = AsyncResult(task_id, app=celery)

        response = {
            'task_id': task_id,
            'state': result.state,
            'ready': result.ready(),
            'successful': result.successful() if result.ready() else None,
            'failed': result.failed() if result.ready() else None,
        }

        # Add result if task is complete
        if result.ready():
            if result.successful():
                response['result'] = result.result
            elif result.failed():
                response['error'] = str(result.info)

        # Add progress info if available
        if hasattr(result, 'info') and isinstance(result.info, dict):
            response['progress'] = result.info.get('progress', 0)
            response['current'] = result.info.get('current', 0)
            response['total'] = result.info.get('total', 100)
            response['status_message'] = result.info.get('status', '')

        return jsonify(response)

    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500


@tasks_bp.route('/api/result/<task_id>')
@login_required
@require_role('admin')
def api_task_result(task_id):
    """Get full result of a completed task."""
    try:
        result = AsyncResult(task_id, app=celery)

        if not result.ready():
            return jsonify({
                'success': False,
                'error': 'Task not yet completed',
                'state': result.state
            }), 400

        if result.successful():
            return jsonify({
                'success': True,
                'state': result.state,
                'result': result.result
            })
        else:
            return jsonify({
                'success': False,
                'state': result.state,
                'error': str(result.info)
            }), 500

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@tasks_bp.route('/api/revoke/<task_id>', methods=['POST'])
@login_required
@require_role('admin')
@audit_action('TASK_REVOKED', 'task')
def api_revoke_task(task_id):
    """Revoke (cancel) a running or pending task."""
    try:
        terminate = request.json.get('terminate', False)

        celery.control.revoke(task_id, terminate=terminate)

        return jsonify({
            'success': True,
            'message': f'Task {task_id} revoked',
            'terminated': terminate
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@tasks_bp.route('/api/stats')
@login_required
@require_role('admin')
def api_stats():
    """Get Celery worker statistics."""
    try:
        inspector = celery.control.inspect()

        stats = inspector.stats() or {}
        active = inspector.active() or {}

        # Calculate totals
        total_workers = len(stats)
        total_active_tasks = sum(len(tasks) for tasks in active.values())

        worker_info = []
        for worker_name, worker_stats in stats.items():
            worker_info.append({
                'name': worker_name,
                'pool': worker_stats.get('pool', {}).get('implementation', 'unknown'),
                'max_concurrency': worker_stats.get('pool', {}).get('max-concurrency', 0),
                'active_tasks': len(active.get(worker_name, []))
            })

        return jsonify({
            'success': True,
            'total_workers': total_workers,
            'total_active_tasks': total_active_tasks,
            'workers': worker_info
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@tasks_bp.route('/api/beat-schedule')
@login_required
@require_role('admin')
def api_beat_schedule():
    """Get Celery Beat scheduled tasks."""
    try:
        from celery.schedules import crontab

        beat_schedule = celery.conf.beat_schedule or {}

        scheduled_tasks = []
        for name, config in beat_schedule.items():
            schedule = config.get('schedule')

            # Format schedule for display
            if isinstance(schedule, crontab):
                schedule_str = f"cron({schedule._orig_minute}, {schedule._orig_hour}, {schedule._orig_day_of_week}, {schedule._orig_day_of_month}, {schedule._orig_month_of_year})"
                # Simplify common patterns
                if str(schedule._orig_minute) == '*':
                    schedule_str = 'Cada minuto'
                elif str(schedule._orig_hour) != '*' and str(schedule._orig_minute) != '*':
                    schedule_str = f"Diario a las {schedule._orig_hour}:{schedule._orig_minute:02d}" if isinstance(schedule._orig_minute, int) else f"Diario a las {schedule._orig_hour}:{schedule._orig_minute}"
            elif hasattr(schedule, 'seconds'):
                schedule_str = f"Cada {schedule.seconds} segundos"
            else:
                schedule_str = str(schedule)

            scheduled_tasks.append({
                'name': name,
                'task': config.get('task', 'unknown'),
                'schedule': schedule_str,
                'args': config.get('args', []),
                'kwargs': config.get('kwargs', {})
            })

        return jsonify({
            'success': True,
            'scheduled_tasks': scheduled_tasks,
            'total': len(scheduled_tasks)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@tasks_bp.route('/api/monitoring-tasks')
@login_required
@require_role('admin')
def api_monitoring_tasks():
    """Get active monitoring tasks from database."""
    try:
        from app.models.monitoring import MonitoringTask, MonitoringStatus
        from datetime import datetime

        # Get active tasks (ACTIVE is the status for running periodic checks)
        tasks = MonitoringTask.query.filter(
            MonitoringTask.status == MonitoringStatus.ACTIVE,
            MonitoringTask.is_deleted == False
        ).order_by(MonitoringTask.next_check_at.asc()).all()

        monitoring_tasks = []
        for task in tasks:
            # Calculate time until next check
            time_until_next = None
            if task.next_check_at:
                delta = task.next_check_at - datetime.utcnow()
                if delta.total_seconds() > 0:
                    minutes = int(delta.total_seconds() / 60)
                    if minutes < 60:
                        time_until_next = f"{minutes} min"
                    else:
                        hours = minutes // 60
                        time_until_next = f"{hours}h {minutes % 60}m"
                else:
                    time_until_next = "Pendiente"

            monitoring_tasks.append({
                'id': task.id,
                'name': task.name,
                'case_id': task.case_id,
                'case_name': task.case.numero_orden if task.case else 'N/A',
                'status': task.status.value,
                'sources_count': task.sources.count() if task.sources else 0,
                'check_interval': task.check_interval_minutes,
                'last_check': task.last_check_at.strftime('%H:%M:%S') if task.last_check_at else 'Nunca',
                'next_check': task.next_check_at.strftime('%H:%M:%S') if task.next_check_at else 'N/A',
                'time_until_next': time_until_next,
                'total_results': task.total_results,
                'alerts_count': task.alerts_count,
                'unread_alerts': task.unread_alerts_count
            })

        return jsonify({
            'success': True,
            'monitoring_tasks': monitoring_tasks,
            'total': len(monitoring_tasks)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@tasks_bp.route('/detail/<task_id>')
@login_required
@require_role('admin')
@audit_action('TASK_DETAIL_VIEWED', 'task')
def task_detail(task_id):
    """View detailed information about a specific task."""
    result = AsyncResult(task_id, app=celery)

    task_info = {
        'id': task_id,
        'state': result.state,
        'ready': result.ready(),
        'successful': result.successful() if result.ready() else None,
        'failed': result.failed() if result.ready() else None,
        'result': None,
        'error': None
    }

    if result.ready():
        if result.successful():
            task_info['result'] = result.result
        elif result.failed():
            task_info['error'] = str(result.info)

    return render_template('tasks/detail.html', task=task_info)
