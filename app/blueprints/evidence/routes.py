"""
Evidence routes.
"""
from flask import render_template, request, redirect, url_for, flash, send_file, jsonify, abort
from flask_login import login_required, current_user
from app.blueprints.evidence import evidence_bp
from app.blueprints.evidence.forms import EvidenceUploadForm, EvidenceSearchForm
from app.models.case import Case
from app.models.evidence import Evidence, EvidenceType, ChainOfCustody
from app.services.evidence_service import EvidenceService
from app.utils.decorators import require_detective, audit_action
from app.extensions import db
from datetime import datetime
import os


@evidence_bp.route('/case/<int:case_id>/evidence')
@login_required
@require_detective()
def case_evidence_list(case_id):
    """List evidence for a case."""
    case = Case.query.get_or_404(case_id)

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        flash('No tiene permiso para ver este caso.', 'danger')
        return redirect(url_for('cases.index'))

    # Get search form
    search_form = EvidenceSearchForm(request.args)

    # Build query
    query = Evidence.query.filter_by(case_id=case_id, is_deleted=False)

    # Apply filters
    if search_form.query.data:
        search_term = f'%{search_form.query.data}%'
        query = query.filter(
            db.or_(
                Evidence.original_filename.ilike(search_term),
                Evidence.description.ilike(search_term),
                Evidence.tags.ilike(search_term)
            )
        )

    if search_form.evidence_type.data:
        try:
            evidence_type = EvidenceType[search_form.evidence_type.data]
            query = query.filter_by(evidence_type=evidence_type)
        except KeyError:
            pass

    if search_form.integrity_status.data:
        if search_form.integrity_status.data == 'verified':
            query = query.filter_by(integrity_verified=True)
        elif search_form.integrity_status.data == 'unverified':
            query = query.filter_by(integrity_verified=False)

    if search_form.date_from.data:
        query = query.filter(Evidence.uploaded_at >= search_form.date_from.data)

    if search_form.date_to.data:
        query = query.filter(Evidence.uploaded_at <= search_form.date_to.data)

    # Order by upload date (newest first)
    evidences = query.order_by(Evidence.uploaded_at.desc()).all()

    # Get statistics
    stats = EvidenceService.get_evidence_stats(case_id=case_id)

    return render_template(
        'evidence/list.html',
        case=case,
        evidences=evidences,
        stats=stats,
        search_form=search_form,
        EvidenceType=EvidenceType
    )


@evidence_bp.route('/case/<int:case_id>/evidence/upload', methods=['GET', 'POST'])
@login_required
@require_detective()
@audit_action('EVIDENCE_UPLOAD_ATTEMPT', 'evidence')
def upload_evidence(case_id):
    """Upload evidence to a case."""
    case = Case.query.get_or_404(case_id)

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        flash('No tiene permiso para subir evidencia a este caso.', 'danger')
        return redirect(url_for('cases.index'))

    form = EvidenceUploadForm()

    if form.validate_on_submit():
        try:
            # Prepare geolocation
            geolocation = None
            if form.latitude.data and form.longitude.data:
                geolocation = {
                    'latitude': float(form.latitude.data),
                    'longitude': float(form.longitude.data)
                }

            # Upload evidence
            evidence = EvidenceService.upload_evidence(
                file=form.file.data,
                case=case,
                user=current_user,
                description=form.description.data,
                tags=form.tags.data,
                acquisition_date=form.acquisition_date.data or datetime.utcnow(),
                acquisition_method=form.acquisition_method.data,
                source_device=form.source_device.data,
                source_location=form.source_location.data,
                acquisition_notes=form.acquisition_notes.data
            )

            # Update geolocation if provided
            if geolocation:
                evidence.geolocation_lat = geolocation['latitude']
                evidence.geolocation_lon = geolocation['longitude']
                db.session.commit()

            flash(f'Evidencia "{evidence.original_filename}" subida correctamente.', 'success')
            return redirect(url_for('evidence.evidence_detail', evidence_id=evidence.id))

        except ValueError as e:
            flash(f'Error al subir evidencia: {str(e)}', 'danger')
        except Exception as e:
            flash(f'Error inesperado: {str(e)}', 'danger')
            db.session.rollback()

    return render_template(
        'evidence/upload.html',
        case=case,
        form=form
    )


@evidence_bp.route('/evidence/<int:evidence_id>')
@login_required
@require_detective()
@audit_action('EVIDENCE_VIEWED', 'evidence')
def evidence_detail(evidence_id):
    """View evidence details."""
    evidence = Evidence.query.get_or_404(evidence_id)
    case = evidence.case

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        flash('No tiene permiso para ver esta evidencia.', 'danger')
        return redirect(url_for('cases.index'))

    # Log view to chain of custody
    ChainOfCustody.log(
        action='VIEWED',
        evidence=evidence,
        user=current_user,
        notes=f'Evidence viewed by {current_user.nombre}'
    )

    # Get chain of custody entries
    custody_entries = ChainOfCustody.query.filter_by(
        evidence_id=evidence_id
    ).order_by(ChainOfCustody.timestamp.desc()).all()

    # Get applicable plugins
    from app.plugins import plugin_manager
    applicable_plugins = plugin_manager.get_applicable_plugins_for_evidence(evidence)

    return render_template(
        'evidence/detail.html',
        evidence=evidence,
        case=case,
        custody_entries=custody_entries,
        EvidenceType=EvidenceType,
        applicable_plugins=applicable_plugins
    )


@evidence_bp.route('/evidence/<int:evidence_id>/verify', methods=['POST'])
@login_required
@require_detective()
@audit_action('EVIDENCE_INTEGRITY_VERIFY', 'evidence')
def verify_integrity(evidence_id):
    """Verify evidence integrity."""
    evidence = Evidence.query.get_or_404(evidence_id)
    case = evidence.case

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        flash('No tiene permiso para verificar esta evidencia.', 'danger')
        return redirect(url_for('cases.index'))

    try:
        result = EvidenceService.verify_evidence_integrity(evidence, current_user)

        if result['verified']:
            flash('Verificación de integridad: ✓ CORRECTA', 'success')
        else:
            flash('⚠️ ALERTA: Verificación de integridad FALLIDA. La evidencia puede estar comprometida.', 'danger')

        return redirect(url_for('evidence.evidence_detail', evidence_id=evidence_id))

    except Exception as e:
        flash(f'Error al verificar integridad: {str(e)}', 'danger')
        return redirect(url_for('evidence.evidence_detail', evidence_id=evidence_id))


@evidence_bp.route('/evidence/<int:evidence_id>/download')
@login_required
@require_detective()
@audit_action('EVIDENCE_DOWNLOADED', 'evidence')
def download_evidence(evidence_id):
    """Download evidence file (decrypted)."""
    evidence = Evidence.query.get_or_404(evidence_id)
    case = evidence.case

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        flash('No tiene permiso para descargar esta evidencia.', 'danger')
        return redirect(url_for('cases.index'))

    try:
        # Get decrypted file path
        decrypted_path = evidence.get_decrypted_path()

        if not os.path.exists(decrypted_path):
            flash('Archivo de evidencia no encontrado.', 'danger')
            return redirect(url_for('evidence.evidence_detail', evidence_id=evidence_id))

        # Verify integrity before download
        result = evidence.verify_integrity()

        # Log download to chain of custody
        ChainOfCustody.log(
            action='DOWNLOADED',
            evidence=evidence,
            user=current_user,
            notes=f'Evidence downloaded by {current_user.nombre}',
            hash_verified=True,
            hash_match=result['verified'],
            sha256=result.get('sha256_calculated'),
            sha512=result.get('sha512_calculated')
        )

        if not result['verified']:
            flash('⚠️ ADVERTENCIA: La integridad de la evidencia NO está verificada. El archivo puede estar comprometido.', 'warning')

        return send_file(
            decrypted_path,
            as_attachment=True,
            download_name=evidence.original_filename,
            mimetype=evidence.mime_type
        )

    except Exception as e:
        flash(f'Error al descargar evidencia: {str(e)}', 'danger')
        return redirect(url_for('evidence.evidence_detail', evidence_id=evidence_id))


@evidence_bp.route('/evidence/<int:evidence_id>/preview')
@login_required
@require_detective()
@audit_action('EVIDENCE_PREVIEWED', 'evidence')
def preview_evidence(evidence_id):
    """Preview evidence file inline (decrypted)."""
    evidence = Evidence.query.get_or_404(evidence_id)
    case = evidence.case

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        abort(403)

    try:
        # Get decrypted file path
        decrypted_path = evidence.get_decrypted_path()

        if not os.path.exists(decrypted_path):
            abort(404)

        # Log preview to chain of custody
        ChainOfCustody.log(
            action='PREVIEWED',
            evidence=evidence,
            user=current_user,
            notes=f'Evidence previewed by {current_user.nombre}'
        )

        # Serve file inline (not as attachment)
        return send_file(
            decrypted_path,
            as_attachment=False,
            download_name=evidence.original_filename,
            mimetype=evidence.mime_type
        )

    except Exception as e:
        abort(500)


@evidence_bp.route('/evidence/<int:evidence_id>/chain-of-custody')
@login_required
@require_detective()
def chain_of_custody(evidence_id):
    """View full chain of custody for evidence."""
    evidence = Evidence.query.get_or_404(evidence_id)
    case = evidence.case

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        flash('No tiene permiso para ver la cadena de custodia de esta evidencia.', 'danger')
        return redirect(url_for('cases.index'))

    # Get all custody entries
    custody_entries = ChainOfCustody.query.filter_by(
        evidence_id=evidence_id
    ).order_by(ChainOfCustody.timestamp.asc()).all()

    return render_template(
        'evidence/chain_of_custody.html',
        evidence=evidence,
        case=case,
        custody_entries=custody_entries
    )


@evidence_bp.route('/evidence/<int:evidence_id>/delete', methods=['POST'])
@login_required
@require_detective()
@audit_action('EVIDENCE_DELETED', 'evidence')
def delete_evidence(evidence_id):
    """Soft delete evidence."""
    evidence = Evidence.query.get_or_404(evidence_id)
    case = evidence.case

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        flash('No tiene permiso para eliminar esta evidencia.', 'danger')
        return redirect(url_for('cases.index'))

    try:
        evidence.soft_delete(current_user)
        flash(f'Evidencia "{evidence.original_filename}" marcada como eliminada.', 'success')
        return redirect(url_for('evidence.case_evidence_list', case_id=case.id))

    except Exception as e:
        flash(f'Error al eliminar evidencia: {str(e)}', 'danger')
        db.session.rollback()
        return redirect(url_for('evidence.evidence_detail', evidence_id=evidence_id))


@evidence_bp.route('/api/evidence/<int:evidence_id>/metadata')
@login_required
@require_detective()
def api_evidence_metadata(evidence_id):
    """API endpoint to get evidence metadata (for future plugin integration)."""
    evidence = Evidence.query.get_or_404(evidence_id)
    case = evidence.case

    # Check access
    if not current_user.is_admin() and case.detective_id != current_user.id:
        abort(403)

    # This will be expanded when plugin system is implemented (Phase 8)
    metadata = {
        'id': evidence.id,
        'filename': evidence.original_filename,
        'type': evidence.evidence_type.value,
        'size': evidence.file_size,
        'mime_type': evidence.mime_type,
        'sha256': evidence.sha256_hash,
        'sha512': evidence.sha512_hash,
        'uploaded_at': evidence.uploaded_at.isoformat(),
        'acquisition_date': evidence.acquisition_date.isoformat() if evidence.acquisition_date else None,
        'acquisition_method': evidence.acquisition_method,
        'integrity_verified': evidence.integrity_verified,
        'last_verification_date': evidence.last_verification_date.isoformat() if evidence.last_verification_date else None
    }

    if evidence.geolocation_lat and evidence.geolocation_lon:
        metadata['geolocation'] = {
            'latitude': evidence.geolocation_lat,
            'longitude': evidence.geolocation_lon
        }

    return jsonify(metadata)
