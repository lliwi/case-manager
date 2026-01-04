"""
Timeline routes.
"""
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from app.blueprints.timeline import timeline_bp
from app.blueprints.timeline.forms import TimelineEventForm, TimelineFilterForm
from app.models.case import Case
from app.models.timeline import TimelineEvent, EventType
from app.services.timeline_service import TimelineService
from app.utils.decorators import require_detective, audit_action
from app.extensions import db


@timeline_bp.route('/case/<int:case_id>/timeline')
@login_required
@require_detective()
@audit_action('TIMELINE_VIEWED', 'timeline')
def case_timeline(case_id):
    """View timeline for a case."""
    case = Case.query.get_or_404(case_id)

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        flash('No tiene permiso para ver este caso.', 'danger')
        return redirect(url_for('cases.index'))

    # Get filter form
    filter_form = TimelineFilterForm(request.args)

    # Build filters dict
    filters = {}
    if filter_form.date_from.data:
        filters['date_from'] = filter_form.date_from.data
    if filter_form.date_to.data:
        filters['date_to'] = filter_form.date_to.data
    if filter_form.event_types.data:
        filters['event_types'] = [EventType[filter_form.event_types.data]]
    if filter_form.subjects.data:
        filters['subjects'] = [s.strip() for s in filter_form.subjects.data.split(',')]
    if filter_form.tags.data:
        filters['tags'] = [t.strip() for t in filter_form.tags.data.split(',')]
    if filter_form.confidence_level.data:
        filters['confidence_levels'] = [filter_form.confidence_level.data]
    if filter_form.has_evidence.data:
        filters['has_evidence'] = filter_form.has_evidence.data == 'yes'

    # Get timeline events
    if filters:
        events = TimelineService.get_filtered_timeline(case_id, filters)
    else:
        events = TimelineService.get_case_timeline(case_id)

    # Get statistics
    stats = TimelineService.get_timeline_stats(case_id)

    return render_template(
        'timeline/timeline.html',
        case=case,
        events=events,
        stats=stats,
        filter_form=filter_form,
        EventType=EventType
    )


@timeline_bp.route('/case/<int:case_id>/timeline/create', methods=['GET', 'POST'])
@login_required
@require_detective()
@audit_action('TIMELINE_EVENT_CREATE', 'timeline')
def create_event(case_id):
    """Create a new timeline event."""
    case = Case.query.get_or_404(case_id)

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        flash('No tiene permiso para editar este caso.', 'danger')
        return redirect(url_for('cases.index'))

    form = TimelineEventForm()

    if form.validate_on_submit():
        try:
            event_data = {
                'event_type': EventType[form.event_type.data],
                'title': form.title.data,
                'description': form.description.data,
                'event_date': form.event_date.data,
                'location_name': form.location_name.data,
                'latitude': form.latitude.data,
                'longitude': form.longitude.data,
                'subjects': form.subjects.data,
                'tags': form.tags.data,
                'confidence_level': form.confidence_level.data,
                'source': form.source.data,
                'color': form.color.data,
                'evidence_id': form.evidence_id.data if form.evidence_id.data else None
            }

            event = TimelineService.create_event(case_id, current_user, event_data)

            flash(f'Evento "{event.title}" creado correctamente.', 'success')
            return redirect(url_for('timeline.case_timeline', case_id=case_id))

        except Exception as e:
            flash(f'Error al crear evento: {str(e)}', 'danger')
            db.session.rollback()

    return render_template(
        'timeline/create_event.html',
        case=case,
        form=form
    )


@timeline_bp.route('/timeline/event/<int:event_id>')
@login_required
@require_detective()
@audit_action('TIMELINE_EVENT_VIEWED', 'timeline')
def event_detail(event_id):
    """View timeline event details."""
    event = TimelineEvent.query.get_or_404(event_id)
    case = event.case

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        flash('No tiene permiso para ver este caso.', 'danger')
        return redirect(url_for('cases.index'))

    return render_template(
        'timeline/event_detail.html',
        event=event,
        case=case,
        EventType=EventType
    )


@timeline_bp.route('/timeline/event/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required
@require_detective()
@audit_action('TIMELINE_EVENT_EDIT', 'timeline')
def edit_event(event_id):
    """Edit timeline event."""
    event = TimelineEvent.query.get_or_404(event_id)
    case = event.case

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        flash('No tiene permiso para editar este evento.', 'danger')
        return redirect(url_for('cases.index'))

    form = TimelineEventForm(obj=event)

    # Pre-populate form on GET
    if request.method == 'GET':
        form.event_type.data = event.event_type.name
        form.event_date.data = event.event_date
        form.confidence_level.data = event.confidence_level or 'medium'

    if form.validate_on_submit():
        try:
            event_data = {
                'title': form.title.data,
                'description': form.description.data,
                'event_date': form.event_date.data,
                'location_name': form.location_name.data,
                'latitude': form.latitude.data,
                'longitude': form.longitude.data,
                'subjects': form.subjects.data,
                'tags': form.tags.data,
                'confidence_level': form.confidence_level.data,
                'source': form.source.data,
                'color': form.color.data
            }

            TimelineService.update_event(event_id, event_data)

            flash(f'Evento "{event.title}" actualizado correctamente.', 'success')
            return redirect(url_for('timeline.event_detail', event_id=event_id))

        except Exception as e:
            flash(f'Error al actualizar evento: {str(e)}', 'danger')
            db.session.rollback()

    return render_template(
        'timeline/edit_event.html',
        event=event,
        case=case,
        form=form
    )


@timeline_bp.route('/timeline/event/<int:event_id>/delete', methods=['POST'])
@login_required
@require_detective()
@audit_action('TIMELINE_EVENT_DELETE', 'timeline')
def delete_event(event_id):
    """Delete timeline event (soft delete)."""
    event = TimelineEvent.query.get_or_404(event_id)
    case = event.case

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        flash('No tiene permiso para eliminar este evento.', 'danger')
        return redirect(url_for('cases.index'))

    try:
        TimelineService.delete_event(event_id, current_user)
        flash(f'Evento "{event.title}" eliminado correctamente.', 'success')
        return redirect(url_for('timeline.case_timeline', case_id=case.id))

    except Exception as e:
        flash(f'Error al eliminar evento: {str(e)}', 'danger')
        return redirect(url_for('timeline.event_detail', event_id=event_id))


@timeline_bp.route('/api/case/<int:case_id>/timeline-data')
@login_required
@require_detective()
def api_timeline_data(case_id):
    """API endpoint to get timeline data for visualization (Vis.js format)."""
    case = Case.query.get_or_404(case_id)

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    # Get filters from query params
    filters = {}
    if request.args.get('date_from'):
        filters['date_from'] = datetime.fromisoformat(request.args.get('date_from'))
    if request.args.get('date_to'):
        filters['date_to'] = datetime.fromisoformat(request.args.get('date_to'))
    if request.args.get('event_type'):
        filters['event_types'] = [EventType[request.args.get('event_type')]]
    if request.args.get('subject'):
        filters['subjects'] = [request.args.get('subject')]

    # Get timeline data in Vis.js format
    timeline_data = TimelineService.get_timeline_for_vis_js(case_id, filters)

    return jsonify(timeline_data)


@timeline_bp.route('/api/case/<int:case_id>/timeline-export')
@login_required
@require_detective()
def api_timeline_export(case_id):
    """API endpoint to export timeline data as JSON."""
    case = Case.query.get_or_404(case_id)

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    # Get export data
    export_data = TimelineService.get_timeline_export_data(case_id)

    return jsonify({
        'case_id': case_id,
        'case_numero_orden': case.numero_orden,
        'export_date': datetime.utcnow().isoformat(),
        'events': export_data
    })


@timeline_bp.route('/case/<int:case_id>/timeline/auto-create', methods=['POST'])
@login_required
@require_detective()
@audit_action('TIMELINE_AUTO_CREATE', 'timeline')
def auto_create_events(case_id):
    """Automatically create timeline events from evidence."""
    case = Case.query.get_or_404(case_id)

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        flash('No tiene permiso para editar este caso.', 'danger')
        return redirect(url_for('cases.index'))

    try:
        count = TimelineService.auto_create_evidence_events(case_id)
        flash(f'Se crearon {count} eventos automáticamente desde las evidencias.', 'success')
    except Exception as e:
        flash(f'Error al crear eventos: {str(e)}', 'danger')

    return redirect(url_for('timeline.case_timeline', case_id=case_id))


@timeline_bp.route('/api/case/<int:case_id>/timeline-patterns')
@login_required
@require_detective()
def api_timeline_patterns(case_id):
    """API endpoint to detect patterns in timeline."""
    case = Case.query.get_or_404(case_id)

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    patterns = TimelineService.detect_patterns(case_id)

    return jsonify(patterns)
