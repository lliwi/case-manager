"""
Libro-registro routes (Official Case Registry per Ley 5/2014).
"""
from flask import render_template, request, send_file, flash, redirect, url_for
from flask_login import login_required, current_user
from app.blueprints.libro_registro import libro_bp
from app.models.case import CaseStatus
from app.models.user import User
from app.services.libro_registro_service import LibroRegistroService
from app.utils.decorators import require_detective
from datetime import datetime
import io


@libro_bp.route('/')
@login_required
@require_detective()
def index():
    """View libro-registro."""
    # Get filter parameters
    year = request.args.get('year', datetime.utcnow().year, type=int)
    detective_id = request.args.get('detective_id', type=int)
    status_filter = request.args.get('status')

    # If not admin, can only see own cases
    if not current_user.is_admin():
        detective_id = current_user.id

    # Convert status filter
    status = None
    if status_filter:
        try:
            status = CaseStatus[status_filter]
        except KeyError:
            pass

    # Get cases
    cases = LibroRegistroService.get_registro_entries(
        detective_id=detective_id,
        year=year,
        status=status,
        include_deleted=False
    ).all()

    # Get statistics
    stats = LibroRegistroService.get_statistics(
        detective_id=detective_id,
        year=year
    )

    # Get available years
    from app.extensions import db
    from sqlalchemy import extract, distinct
    available_years = db.session.query(
        distinct(extract('year', db.Model.metadata.tables['cases'].c.fecha_inicio))
    ).order_by(extract('year', db.Model.metadata.tables['cases'].c.fecha_inicio).desc()).all()
    available_years = [y[0] for y in available_years if y[0]]

    # Get detectives (for admin)
    detectives = []
    if current_user.is_admin():
        detectives = User.query.filter(
            User.roles.any(name='detective')
        ).all()

    return render_template(
        'libro/index.html',
        cases=cases,
        stats=stats,
        year=year,
        available_years=available_years,
        detectives=detectives,
        selected_detective_id=detective_id,
        CaseStatus=CaseStatus
    )


@libro_bp.route('/export/csv')
@login_required
@require_detective()
def export_csv():
    """Export libro-registro to CSV."""
    year = request.args.get('year', datetime.utcnow().year, type=int)
    detective_id = request.args.get('detective_id', type=int)

    # If not admin, can only export own cases
    if not current_user.is_admin():
        detective_id = current_user.id

    # Get cases
    cases = LibroRegistroService.get_registro_entries(
        detective_id=detective_id,
        year=year,
        include_deleted=False
    ).all()

    # Generate CSV
    csv_data = LibroRegistroService.export_to_csv(cases, include_personal_data=True)

    # Create file-like object
    output = io.BytesIO()
    output.write(csv_data.encode('utf-8-sig'))  # UTF-8 with BOM for Excel
    output.seek(0)

    # Determine filename
    if detective_id and current_user.is_admin():
        detective = User.query.get(detective_id)
        filename = f"libro_registro_{year}_{detective.tip_number}.csv"
    else:
        filename = f"libro_registro_{year}_{current_user.tip_number}.csv"

    return send_file(
        output,
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename
    )


@libro_bp.route('/statistics')
@login_required
@require_detective()
def statistics():
    """View detailed statistics."""
    year = request.args.get('year', datetime.utcnow().year, type=int)
    detective_id = request.args.get('detective_id', type=int)

    # If not admin, can only see own stats
    if not current_user.is_admin():
        detective_id = current_user.id

    # Get statistics
    stats = LibroRegistroService.get_statistics(
        detective_id=detective_id,
        year=year
    )

    return render_template(
        'libro/statistics.html',
        stats=stats,
        year=year
    )


@libro_bp.route('/compliance-check')
@login_required
@require_detective()
def compliance_check():
    """Check compliance with Ley 5/2014."""
    # Only admin can run compliance check
    if not current_user.is_admin():
        flash('Solo los administradores pueden ejecutar la verificación de cumplimiento.', 'danger')
        return redirect(url_for('libro_registro.index'))

    # Run compliance check
    compliance = LibroRegistroService.verify_compliance()

    return render_template(
        'libro/compliance.html',
        compliance=compliance
    )
