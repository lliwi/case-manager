"""
Monitoring routes for task and source management.

Provides web interface for:
- Creating and managing monitoring tasks
- Adding and managing data sources
- Viewing and acknowledging results
- Saving results as evidence
"""
from datetime import datetime
from flask import (
    render_template, redirect, url_for, flash, request, jsonify, abort
)
from flask_login import login_required, current_user

from app.blueprints.monitoring import monitoring_bp
from app.blueprints.monitoring.forms import (
    MonitoringTaskForm, MonitoringSourceForm,
    AlertAcknowledgeForm, SaveAsEvidenceForm
)
from app.extensions import db
from app.models.case import Case, CaseStatus
from app.models.monitoring import (
    MonitoringTask, MonitoringSource, MonitoringResult, MonitoringCheckLog,
    MonitoringStatus, SourcePlatform, SourceQueryType
)
from app.models.audit import AuditLog
from app.services.monitoring_service import MonitoringService
from app.tasks.monitoring_tasks import execute_single_check


def get_case_or_404(case_id):
    """Get case or abort with 404."""
    case = Case.query.filter_by(id=case_id, is_deleted=False).first()
    if not case:
        abort(404)

    # Check user has access
    if case.detective_id != current_user.id and not current_user.is_admin:
        abort(403)

    return case


def get_task_or_404(task_id, case_id=None):
    """Get monitoring task or abort with 404."""
    query = MonitoringTask.query.filter_by(id=task_id, is_deleted=False)
    if case_id:
        query = query.filter_by(case_id=case_id)
    task = query.first()

    if not task:
        abort(404)

    # Check user has access
    if task.case.detective_id != current_user.id and not current_user.is_admin:
        abort(403)

    return task


# ============================================================================
# Task Routes
# ============================================================================

@monitoring_bp.route('/case/<int:case_id>')
@login_required
def task_list(case_id):
    """List all monitoring tasks for a case."""
    case = get_case_or_404(case_id)

    tasks = MonitoringTask.query.filter_by(
        case_id=case_id,
        is_deleted=False
    ).order_by(MonitoringTask.created_at.desc()).all()

    # Calculate total unread alerts
    total_unread = sum(t.unread_alerts_count for t in tasks)

    return render_template(
        'monitoring/task_list.html',
        case=case,
        tasks=tasks,
        total_unread=total_unread
    )


@monitoring_bp.route('/case/<int:case_id>/create', methods=['GET', 'POST'])
@login_required
def task_create(case_id):
    """Create a new monitoring task."""
    case = get_case_or_404(case_id)

    # Check case status
    if case.status not in (CaseStatus.EN_INVESTIGACION, CaseStatus.PENDIENTE_VALIDACION):
        flash('No se pueden crear tareas de monitorización en casos cerrados o archivados.', 'warning')
        return redirect(url_for('monitoring.task_list', case_id=case_id))

    form = MonitoringTaskForm()

    # Set default start date to now
    if request.method == 'GET':
        form.start_date.data = datetime.utcnow()

    if form.validate_on_submit():
        try:
            task = MonitoringService.create_task(
                case_id=case_id,
                name=form.name.data,
                monitoring_objective=form.monitoring_objective.data,
                user_id=current_user.id,
                start_date=form.start_date.data,
                description=form.description.data,
                ai_provider=form.ai_provider.data,
                ai_analysis_enabled=form.ai_analysis_enabled.data,
                check_interval_minutes=form.check_interval_minutes.data,
                end_date=form.end_date.data,
                ai_prompt_template=form.ai_prompt_template.data
            )

            AuditLog.log(
                action='MONITORING_TASK_CREATED',
                resource_type='monitoring_task',
                resource_id=task.id,
                user=current_user,
                description=f'Created monitoring task "{task.name}"',
                extra_data={'case_id': case_id}
            )

            flash('Tarea de monitorización creada. Añade al menos una fuente de datos.', 'success')
            return redirect(url_for('monitoring.task_detail', case_id=case_id, task_id=task.id))

        except Exception as e:
            flash(f'Error al crear la tarea: {str(e)}', 'danger')

    return render_template(
        'monitoring/task_form.html',
        case=case,
        form=form,
        is_edit=False
    )


@monitoring_bp.route('/case/<int:case_id>/<int:task_id>')
@login_required
def task_detail(case_id, task_id):
    """View monitoring task details."""
    case = get_case_or_404(case_id)
    task = get_task_or_404(task_id, case_id)

    # Get sources
    sources = task.sources.order_by(MonitoringSource.created_at.desc()).all()

    # Get recent results
    recent_results = task.results.order_by(
        MonitoringResult.captured_at.desc()
    ).limit(20).all()

    # Get recent check logs
    recent_logs = task.check_logs.order_by(
        MonitoringCheckLog.check_started_at.desc()
    ).limit(10).all()

    # Get statistics
    stats = MonitoringService.get_task_statistics(task_id)

    return render_template(
        'monitoring/task_detail.html',
        case=case,
        task=task,
        sources=sources,
        recent_results=recent_results,
        recent_logs=recent_logs,
        stats=stats
    )


@monitoring_bp.route('/case/<int:case_id>/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def task_edit(case_id, task_id):
    """Edit a monitoring task."""
    case = get_case_or_404(case_id)
    task = get_task_or_404(task_id, case_id)

    form = MonitoringTaskForm(obj=task)

    # Set the ai_provider value correctly for the form
    if request.method == 'GET' and task.ai_provider:
        form.ai_provider.data = task.ai_provider.value

    if form.validate_on_submit():
        try:
            MonitoringService.update_task(
                task_id=task_id,
                name=form.name.data,
                description=form.description.data,
                monitoring_objective=form.monitoring_objective.data,
                ai_provider=form.ai_provider.data,
                ai_analysis_enabled=form.ai_analysis_enabled.data,
                ai_prompt_template=form.ai_prompt_template.data,
                check_interval_minutes=form.check_interval_minutes.data,
                start_date=form.start_date.data,
                end_date=form.end_date.data
            )

            AuditLog.log(
                action='MONITORING_TASK_UPDATED',
                resource_type='monitoring_task',
                resource_id=task_id,
                user=current_user,
                description=f'Updated monitoring task'
            )

            flash('Tarea actualizada correctamente.', 'success')
            return redirect(url_for('monitoring.task_detail', case_id=case_id, task_id=task_id))

        except Exception as e:
            flash(f'Error al actualizar: {str(e)}', 'danger')

    return render_template(
        'monitoring/task_form.html',
        case=case,
        task=task,
        form=form,
        is_edit=True
    )


@monitoring_bp.route('/case/<int:case_id>/<int:task_id>/toggle-status', methods=['POST'])
@login_required
def task_toggle_status(case_id, task_id):
    """Toggle task status between active and paused."""
    task = get_task_or_404(task_id, case_id)

    success, message = MonitoringService.toggle_task_status(task_id, current_user.id)

    if success:
        AuditLog.log(
            action='MONITORING_TASK_STATUS_CHANGED',
            resource_type='monitoring_task',
            resource_id=task_id,
            user=current_user,
            description=f'Changed task status to {task.status.value}'
        )
        flash(message, 'success')
    else:
        flash(message, 'warning')

    return redirect(url_for('monitoring.task_detail', case_id=case_id, task_id=task_id))


@monitoring_bp.route('/case/<int:case_id>/<int:task_id>/run-now', methods=['POST'])
@login_required
def task_run_now(case_id, task_id):
    """Trigger immediate monitoring check."""
    task = get_task_or_404(task_id, case_id)

    if task.sources.count() == 0:
        flash('La tarea debe tener al menos una fuente de datos.', 'warning')
        return redirect(url_for('monitoring.task_detail', case_id=case_id, task_id=task_id))

    try:
        # Queue the task
        execute_single_check.delay(
            task_id=task_id,
            triggered_by='manual',
            user_id=current_user.id
        )

        AuditLog.log(
            action='MONITORING_MANUAL_CHECK_TRIGGERED',
            resource_type='monitoring_task',
            resource_id=task_id,
            user=current_user,
            description='Triggered manual monitoring check'
        )

        flash('Comprobación iniciada. Los resultados aparecerán en unos momentos.', 'info')

    except Exception as e:
        flash(f'Error al iniciar la comprobación: {str(e)}', 'danger')

    return redirect(url_for('monitoring.task_detail', case_id=case_id, task_id=task_id))


@monitoring_bp.route('/case/<int:case_id>/<int:task_id>/delete', methods=['POST'])
@login_required
def task_delete(case_id, task_id):
    """Delete a monitoring task."""
    task = get_task_or_404(task_id, case_id)

    try:
        MonitoringService.delete_task(task_id, current_user.id)

        AuditLog.log(
            action='MONITORING_TASK_DELETED',
            resource_type='monitoring_task',
            resource_id=task_id,
            user=current_user,
            description='Deleted monitoring task',
            extra_data={'case_id': case_id}
        )

        flash('Tarea eliminada correctamente.', 'success')

    except Exception as e:
        flash(f'Error al eliminar: {str(e)}', 'danger')

    return redirect(url_for('monitoring.task_list', case_id=case_id))


# ============================================================================
# Source Routes
# ============================================================================

@monitoring_bp.route('/case/<int:case_id>/<int:task_id>/sources/add', methods=['GET', 'POST'])
@login_required
def source_add(case_id, task_id):
    """Add a new monitoring source."""
    case = get_case_or_404(case_id)
    task = get_task_or_404(task_id, case_id)

    form = MonitoringSourceForm()

    if form.validate_on_submit():
        try:
            source = MonitoringService.add_source(
                task_id=task_id,
                platform=form.platform.data,
                query_type=form.query_type.data,
                query_value=form.query_value.data,
                max_results_per_check=form.max_results_per_check.data or 20,
                include_media=form.include_media.data
            )

            AuditLog.log(
                action='MONITORING_SOURCE_ADDED',
                resource_type='monitoring_source',
                resource_id=source.id,
                user=current_user,
                description=f'Added {source.platform.value} source',
                extra_data={
                    'task_id': task_id,
                    'platform': form.platform.data,
                    'query_value': form.query_value.data
                }
            )

            flash('Fuente añadida correctamente.', 'success')
            return redirect(url_for('monitoring.task_detail', case_id=case_id, task_id=task_id))

        except Exception as e:
            flash(f'Error al añadir la fuente: {str(e)}', 'danger')

    return render_template(
        'monitoring/source_form.html',
        case=case,
        task=task,
        form=form,
        is_edit=False
    )


@monitoring_bp.route('/case/<int:case_id>/<int:task_id>/sources/<int:source_id>/delete', methods=['POST'])
@login_required
def source_delete(case_id, task_id, source_id):
    """Delete a monitoring source."""
    task = get_task_or_404(task_id, case_id)

    source = MonitoringSource.query.filter_by(
        id=source_id,
        task_id=task_id
    ).first()

    if not source:
        abort(404)

    try:
        db.session.delete(source)
        db.session.commit()

        AuditLog.log(
            action='MONITORING_SOURCE_DELETED',
            resource_type='monitoring_source',
            resource_id=source_id,
            user=current_user,
            description='Deleted monitoring source',
            extra_data={'task_id': task_id}
        )

        flash('Fuente eliminada correctamente.', 'success')

    except Exception as e:
        flash(f'Error al eliminar: {str(e)}', 'danger')

    return redirect(url_for('monitoring.task_detail', case_id=case_id, task_id=task_id))


# ============================================================================
# Results Routes
# ============================================================================

@monitoring_bp.route('/case/<int:case_id>/<int:task_id>/results')
@login_required
def results_list(case_id, task_id):
    """View all results for a monitoring task."""
    case = get_case_or_404(case_id)
    task = get_task_or_404(task_id, case_id)

    # Get filters
    filter_alerts = request.args.get('alerts', 'all')
    filter_analyzed = request.args.get('analyzed', 'all')
    page = request.args.get('page', 1, type=int)

    # Build query
    query = task.results

    if filter_alerts == 'only':
        query = query.filter_by(is_alert=True)
    elif filter_alerts == 'pending':
        query = query.filter_by(is_alert=True, alert_acknowledged=False)

    if filter_analyzed == 'yes':
        query = query.filter_by(ai_analyzed=True)
    elif filter_analyzed == 'no':
        query = query.filter_by(ai_analyzed=False)

    # Paginate
    results = query.order_by(
        MonitoringResult.captured_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)

    return render_template(
        'monitoring/results.html',
        case=case,
        task=task,
        results=results,
        filter_alerts=filter_alerts,
        filter_analyzed=filter_analyzed
    )


@monitoring_bp.route('/case/<int:case_id>/<int:task_id>/results/<int:result_id>')
@login_required
def result_detail(case_id, task_id, result_id):
    """View a single result detail."""
    case = get_case_or_404(case_id)
    task = get_task_or_404(task_id, case_id)

    result = MonitoringResult.query.filter_by(
        id=result_id,
        task_id=task_id
    ).first()

    if not result:
        abort(404)

    acknowledge_form = AlertAcknowledgeForm()
    evidence_form = SaveAsEvidenceForm()

    return render_template(
        'monitoring/result_detail.html',
        case=case,
        task=task,
        result=result,
        acknowledge_form=acknowledge_form,
        evidence_form=evidence_form
    )


@monitoring_bp.route('/case/<int:case_id>/<int:task_id>/results/<int:result_id>/acknowledge', methods=['POST'])
@login_required
def result_acknowledge(case_id, task_id, result_id):
    """Acknowledge an alert."""
    task = get_task_or_404(task_id, case_id)

    result = MonitoringResult.query.filter_by(
        id=result_id,
        task_id=task_id
    ).first()

    if not result:
        abort(404)

    form = AlertAcknowledgeForm()

    if form.validate_on_submit():
        try:
            result.acknowledge_alert(current_user.id, form.alert_notes.data)
            db.session.commit()

            AuditLog.log(
                action='MONITORING_ALERT_ACKNOWLEDGED',
                resource_type='monitoring_result',
                resource_id=result_id,
                user=current_user,
                description='Acknowledged monitoring alert',
                extra_data={'task_id': task_id}
            )

            flash('Alerta reconocida.', 'success')

        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')

    return redirect(url_for('monitoring.result_detail', case_id=case_id, task_id=task_id, result_id=result_id))


@monitoring_bp.route('/case/<int:case_id>/<int:task_id>/results/<int:result_id>/save-evidence', methods=['POST'])
@login_required
def result_save_evidence(case_id, task_id, result_id):
    """Save a result as case evidence."""
    task = get_task_or_404(task_id, case_id)

    result = MonitoringResult.query.filter_by(
        id=result_id,
        task_id=task_id
    ).first()

    if not result:
        abort(404)

    if result.saved_as_evidence:
        flash('Este resultado ya ha sido guardado como evidencia.', 'warning')
        return redirect(url_for('monitoring.result_detail', case_id=case_id, task_id=task_id, result_id=result_id))

    form = SaveAsEvidenceForm()

    if form.validate_on_submit():
        try:
            evidence = MonitoringService.save_result_as_evidence(
                result_id=result_id,
                user_id=current_user.id,
                description=form.description.data
            )

            if evidence:
                AuditLog.log(
                    action='MONITORING_RESULT_SAVED_AS_EVIDENCE',
                    resource_type='evidence',
                    resource_id=evidence.id,
                    user=current_user,
                    description='Saved monitoring result as evidence',
                    extra_data={
                        'result_id': result_id,
                        'case_id': case_id
                    }
                )

                flash(f'Guardado como evidencia #{evidence.id}.', 'success')
            else:
                flash('No se pudo guardar como evidencia.', 'danger')

        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')

    return redirect(url_for('monitoring.result_detail', case_id=case_id, task_id=task_id, result_id=result_id))


# ============================================================================
# Check Logs Routes
# ============================================================================

@monitoring_bp.route('/case/<int:case_id>/<int:task_id>/logs')
@login_required
def check_logs(case_id, task_id):
    """View check execution logs."""
    case = get_case_or_404(case_id)
    task = get_task_or_404(task_id, case_id)

    page = request.args.get('page', 1, type=int)

    logs = task.check_logs.order_by(
        MonitoringCheckLog.check_started_at.desc()
    ).paginate(page=page, per_page=30, error_out=False)

    return render_template(
        'monitoring/check_logs.html',
        case=case,
        task=task,
        logs=logs
    )


# ============================================================================
# API Routes (for AJAX)
# ============================================================================

@monitoring_bp.route('/api/task/<int:task_id>/stats')
@login_required
def api_task_stats(task_id):
    """Get task statistics as JSON."""
    task = get_task_or_404(task_id)
    stats = MonitoringService.get_task_statistics(task_id)
    return jsonify(stats)


@monitoring_bp.route('/api/task/<int:task_id>/recent-results')
@login_required
def api_recent_results(task_id):
    """Get recent results as JSON."""
    task = get_task_or_404(task_id)

    limit = request.args.get('limit', 10, type=int)
    since_id = request.args.get('since_id', type=int)

    query = task.results.order_by(MonitoringResult.captured_at.desc())

    if since_id:
        query = query.filter(MonitoringResult.id > since_id)

    results = query.limit(limit).all()

    return jsonify({
        'results': [r.to_dict() for r in results],
        'count': len(results),
        'latest_id': results[0].id if results else since_id
    })


@monitoring_bp.route('/api/task/<int:task_id>/new-results-count')
@login_required
def api_new_results_count(task_id):
    """Get count of new results since a given ID."""
    task = get_task_or_404(task_id)

    since_id = request.args.get('since_id', 0, type=int)

    count = task.results.filter(MonitoringResult.id > since_id).count()

    latest = task.results.order_by(MonitoringResult.captured_at.desc()).first()
    latest_id = latest.id if latest else 0

    return jsonify({
        'new_count': count,
        'latest_id': latest_id,
        'total': task.results.count()
    })
