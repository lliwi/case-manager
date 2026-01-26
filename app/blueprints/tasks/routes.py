"""
Task monitoring routes.
"""
from flask import render_template, jsonify, request
from flask_login import login_required, current_user
from app.blueprints.tasks import tasks_bp
from app.utils.decorators import require_role
from app.extensions import limiter
from celery.result import AsyncResult
from datetime import datetime, timedelta


# Exempt task API endpoints from default rate limiting (they poll frequently)
@tasks_bp.before_request
def exempt_tasks_api():
    """Exempt /tasks/api/* from rate limiting for monitor polling."""
    pass  # The exemption is applied via decorator below


@tasks_bp.route('/monitor')
@login_required
@require_role('admin')
def monitor():
    """Task monitoring dashboard."""
    return render_template('tasks/monitor.html')


@tasks_bp.route('/status/<task_id>')
@login_required
@require_role('admin')
def task_status(task_id):
    """Get status of a specific task."""
    task = AsyncResult(task_id)

    response = {
        'task_id': task_id,
        'state': task.state,
        'ready': task.ready(),
        'successful': task.successful() if task.ready() else None,
        'info': None,
        'result': None
    }

    if task.state == 'PENDING':
        response['info'] = {'status': 'Pendiente...', 'progress': 0}
    elif task.state == 'PROGRESS':
        response['info'] = task.info
    elif task.state == 'SUCCESS':
        response['result'] = task.result
        response['info'] = {'status': 'Completado', 'progress': 100}
    elif task.state == 'FAILURE':
        response['info'] = {'status': 'Error', 'error': str(task.result)}

    return jsonify(response)


@tasks_bp.route('/api/task/<task_id>')
@limiter.exempt
@login_required
@require_role('admin')
def api_task_status(task_id):
    """API endpoint to get task status for the monitor UI."""
    task = AsyncResult(task_id)

    response = {
        'task_id': task_id,
        'state': task.state,
        'ready': task.ready(),
        'successful': task.successful() if task.ready() else None,
        'progress': None,
        'result': None,
        'error': None
    }

    if task.state == 'PENDING':
        response['progress'] = 0
    elif task.state == 'PROGRESS':
        if task.info and isinstance(task.info, dict):
            response['progress'] = task.info.get('progress', 0)
    elif task.state == 'SUCCESS':
        response['result'] = task.result
        response['progress'] = 100
    elif task.state == 'FAILURE':
        response['error'] = str(task.result)

    return jsonify(response)


@tasks_bp.route('/api/revoke/<task_id>', methods=['POST'])
@limiter.exempt
@login_required
@require_role('admin')
def api_revoke_task(task_id):
    """API endpoint to revoke/cancel a task."""
    from app.tasks.celery_app import celery

    try:
        data = request.get_json() or {}
        terminate = data.get('terminate', False)

        celery.control.revoke(task_id, terminate=terminate)

        return jsonify({'success': True, 'message': f'Tarea {task_id} cancelada'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@tasks_bp.route('/api/list')
@limiter.exempt
@login_required
@require_role('admin')
def api_list_tasks():
    """API endpoint to list all active/scheduled/reserved tasks."""
    from app.tasks.celery_app import celery

    try:
        inspector = celery.control.inspect()
        tasks = []

        # Get active tasks
        active = inspector.active() or {}
        for worker, worker_tasks in active.items():
            for task in worker_tasks:
                tasks.append({
                    'id': task.get('id'),
                    'name': task.get('name', 'Unknown'),
                    'worker': worker.split('@')[-1] if '@' in worker else worker,
                    'state': 'ACTIVE',
                    'args': task.get('args', []),
                    'kwargs': task.get('kwargs', {})
                })

        # Get reserved tasks
        reserved = inspector.reserved() or {}
        for worker, worker_tasks in reserved.items():
            for task in worker_tasks:
                tasks.append({
                    'id': task.get('id'),
                    'name': task.get('name', 'Unknown'),
                    'worker': worker.split('@')[-1] if '@' in worker else worker,
                    'state': 'RESERVED',
                    'args': task.get('args', []),
                    'kwargs': task.get('kwargs', {})
                })

        # Get scheduled tasks
        scheduled = inspector.scheduled() or {}
        for worker, worker_tasks in scheduled.items():
            for task in worker_tasks:
                request_info = task.get('request', {})
                tasks.append({
                    'id': request_info.get('id') or task.get('id'),
                    'name': request_info.get('name') or task.get('name', 'Unknown'),
                    'worker': worker.split('@')[-1] if '@' in worker else worker,
                    'state': 'SCHEDULED',
                    'eta': task.get('eta')
                })

        return jsonify({'success': True, 'tasks': tasks})
    except Exception as e:
        return jsonify({'success': False, 'tasks': [], 'error': str(e)})


@tasks_bp.route('/api/stats')
@limiter.exempt
@login_required
@require_role('admin')
def api_stats():
    """API endpoint to get worker statistics."""
    from app.tasks.celery_app import celery

    try:
        inspector = celery.control.inspect()
        stats = inspector.stats() or {}
        active = inspector.active() or {}

        workers = []
        for worker_name, worker_stats in stats.items():
            pool_info = worker_stats.get('pool', {})
            active_tasks = active.get(worker_name, [])

            workers.append({
                'name': worker_name.split('@')[-1] if '@' in worker_name else worker_name,
                'pool': pool_info.get('implementation', 'unknown').split('.')[-1],
                'max_concurrency': pool_info.get('max-concurrency', 0),
                'active_tasks': len(active_tasks)
            })

        return jsonify({
            'success': True,
            'total_workers': len(workers),
            'workers': workers
        })
    except Exception as e:
        return jsonify({'success': False, 'total_workers': 0, 'workers': [], 'error': str(e)})


@tasks_bp.route('/api/beat')
@limiter.exempt
@login_required
@require_role('admin')
def api_beat_schedule():
    """API endpoint to get Celery Beat scheduled tasks."""
    from app.tasks.celery_app import celery

    try:
        scheduled_tasks = []

        # Get beat schedule from celery config
        beat_schedule = celery.conf.get('beat_schedule', {})

        for name, config in beat_schedule.items():
            schedule = config.get('schedule', '')
            if hasattr(schedule, 'run_every'):
                schedule_str = f"Cada {schedule.run_every}"
            elif hasattr(schedule, 'crontab'):
                schedule_str = str(schedule)
            else:
                schedule_str = str(schedule)

            scheduled_tasks.append({
                'name': name,
                'task': config.get('task', 'Unknown'),
                'schedule': schedule_str
            })

        return jsonify({
            'success': True,
            'total': len(scheduled_tasks),
            'scheduled_tasks': scheduled_tasks
        })
    except Exception as e:
        return jsonify({'success': False, 'total': 0, 'scheduled_tasks': [], 'error': str(e)})


@tasks_bp.route('/api/monitoring')
@limiter.exempt
@login_required
@require_role('admin')
def api_monitoring_tasks():
    """API endpoint to get active monitoring tasks from DB."""
    try:
        from app.models.monitoring import MonitoringTask, MonitoringStatus
        from app.models.case import Case

        # Filter by active status and not deleted
        tasks = MonitoringTask.query.filter(
            MonitoringTask.status == MonitoringStatus.ACTIVE,
            MonitoringTask.is_deleted == False
        ).all()

        monitoring_tasks = []
        now = datetime.utcnow()

        for task in tasks:
            case = Case.query.get(task.case_id)

            # Calculate next check time
            time_until_next = None
            if task.next_check_at and task.next_check_at > now:
                delta = task.next_check_at - now
                if delta.seconds < 3600:
                    time_until_next = f"{delta.seconds // 60} min"
                else:
                    time_until_next = f"{delta.seconds // 3600}h {(delta.seconds % 3600) // 60}m"

            monitoring_tasks.append({
                'id': task.id,
                'name': task.name,
                'case_id': task.case_id,
                'case_name': case.numero_orden if case else 'Unknown',
                'sources_count': task.sources.count() if task.sources else 0,
                'check_interval': task.check_interval_minutes,
                'last_check': task.last_check_at.strftime('%d/%m %H:%M') if task.last_check_at else 'Nunca',
                'next_check': task.next_check_at.strftime('%d/%m %H:%M') if task.next_check_at else 'Pendiente',
                'time_until_next': time_until_next,
                'total_results': task.total_results,
                'alerts_count': task.alerts_count,
                'unread_alerts': task.unread_alerts_count
            })

        return jsonify({
            'success': True,
            'total': len(monitoring_tasks),
            'monitoring_tasks': monitoring_tasks
        })
    except Exception as e:
        return jsonify({'success': False, 'total': 0, 'monitoring_tasks': [], 'error': str(e)})


@tasks_bp.route('/active')
@login_required
@require_role('admin')
def active_tasks():
    """Get list of active tasks from Celery."""
    from app.tasks.celery_app import celery

    inspector = celery.control.inspect()

    result = {
        'active': {},
        'reserved': {},
        'scheduled': {},
        'stats': {}
    }

    try:
        active = inspector.active()
        if active:
            result['active'] = active

        reserved = inspector.reserved()
        if reserved:
            result['reserved'] = reserved

        scheduled = inspector.scheduled()
        if scheduled:
            result['scheduled'] = scheduled

        stats = inspector.stats()
        if stats:
            result['stats'] = stats

    except Exception as e:
        result['error'] = str(e)

    return jsonify(result)
