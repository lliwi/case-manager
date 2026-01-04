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
