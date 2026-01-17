"""
Report routes for managing forensic investigation reports.
"""
from flask import render_template, request, jsonify, flash, redirect, url_for, send_file
from flask_login import login_required, current_user
from app.blueprints.reports import reports_bp
from app.models.report import Report, ReportType, ReportStatus
from app.models.case import Case
from app.services.report_service import ReportService
from app.utils.decorators import audit_action
from app.extensions import db
import os


@reports_bp.route('/case/<int:case_id>/reports')
@login_required
@audit_action('REPORTS_LIST_VIEWED', 'report')
def case_reports(case_id):
    """List all reports for a case."""
    case = Case.query.get_or_404(case_id)

    # Check permissions
    if case.detective_id != current_user.id and not current_user.has_role('admin'):
        flash('No tienes permisos para acceder a este caso', 'error')
        return redirect(url_for('cases.index'))

    # Get all reports for this case
    reports = Report.query.filter_by(
        case_id=case_id,
        is_deleted=False
    ).order_by(Report.created_at.desc()).all()

    return render_template(
        'reports/case_reports.html',
        case=case,
        reports=reports
    )


@reports_bp.route('/case/<int:case_id>/reports/create', methods=['GET', 'POST'])
@login_required
@audit_action('REPORT_CREATE', 'report')
def create_report(case_id):
    """Create a new report for a case."""
    case = Case.query.get_or_404(case_id)

    # Check permissions
    if case.detective_id != current_user.id and not current_user.has_role('admin'):
        flash('No tienes permisos para crear informes en este caso', 'error')
        return redirect(url_for('cases.index'))

    if request.method == 'GET':
        return render_template(
            'reports/create_report.html',
            case=case,
            report_types=ReportType
        )

    # POST - Create report
    report_type_value = request.form.get('report_type')
    title = request.form.get('title')
    description = request.form.get('description')
    introduction = request.form.get('introduction')
    methodology = request.form.get('methodology')
    findings = request.form.get('findings')
    conclusions = request.form.get('conclusions')
    recommendations = request.form.get('recommendations')

    # Include options
    include_evidence_list = request.form.get('include_evidence_list') == 'on'
    include_timeline = request.form.get('include_timeline') == 'on'
    include_graph = request.form.get('include_graph') == 'on'
    include_chain_of_custody = request.form.get('include_chain_of_custody') == 'on'
    include_plugin_results = request.form.get('include_plugin_results') == 'on'
    include_evidence_thumbnails = request.form.get('include_evidence_thumbnails') == 'on'
    include_osint_contacts = request.form.get('include_osint_contacts') == 'on'

    if not title:
        flash('El título es requerido', 'error')
        return redirect(url_for('reports.create_report', case_id=case_id))

    # Convert report type
    report_type = ReportType[report_type_value]

    # Create report
    report = ReportService.create_report(
        case_id=case_id,
        created_by_id=current_user.id,
        report_type=report_type,
        title=title,
        description=description,
        introduction=introduction,
        methodology=methodology,
        findings=findings,
        conclusions=conclusions,
        recommendations=recommendations,
        include_evidence_list=include_evidence_list,
        include_timeline=include_timeline,
        include_graph=include_graph,
        include_chain_of_custody=include_chain_of_custody,
        include_plugin_results=include_plugin_results,
        include_evidence_thumbnails=include_evidence_thumbnails,
        include_osint_contacts=include_osint_contacts
    )

    flash(f'Informe "{title}" creado exitosamente', 'success')
    return redirect(url_for('reports.report_detail', report_id=report.id))


@reports_bp.route('/report/<int:report_id>')
@login_required
@audit_action('REPORT_VIEWED', 'report')
def report_detail(report_id):
    """View report details."""
    report = Report.query.get_or_404(report_id)

    # Check permissions
    if report.case.detective_id != current_user.id and not current_user.has_role('admin'):
        flash('No tienes permisos para acceder a este informe', 'error')
        return redirect(url_for('cases.index'))

    return render_template(
        'reports/report_detail.html',
        report=report
    )


@reports_bp.route('/report/<int:report_id>/edit', methods=['GET', 'POST'])
@login_required
@audit_action('REPORT_EDIT', 'report')
def edit_report(report_id):
    """Edit a report."""
    report = Report.query.get_or_404(report_id)

    # Check permissions
    if report.case.detective_id != current_user.id and not current_user.has_role('admin'):
        flash('No tienes permisos para editar este informe', 'error')
        return redirect(url_for('cases.index'))

    # Can only edit drafts
    if report.status != ReportStatus.DRAFT:
        flash('Solo se pueden editar informes en estado borrador', 'error')
        return redirect(url_for('reports.report_detail', report_id=report_id))

    if request.method == 'GET':
        return render_template(
            'reports/edit_report.html',
            report=report,
            report_types=ReportType
        )

    # POST - Update report
    report.title = request.form.get('title', report.title)
    report.description = request.form.get('description')
    report.introduction = request.form.get('introduction')
    report.methodology = request.form.get('methodology')
    report.findings = request.form.get('findings')
    report.conclusions = request.form.get('conclusions')
    report.recommendations = request.form.get('recommendations')

    # Include options
    report.include_evidence_list = request.form.get('include_evidence_list') == 'on'
    report.include_timeline = request.form.get('include_timeline') == 'on'
    report.include_graph = request.form.get('include_graph') == 'on'
    report.include_chain_of_custody = request.form.get('include_chain_of_custody') == 'on'
    report.include_plugin_results = request.form.get('include_plugin_results') == 'on'
    report.include_evidence_thumbnails = request.form.get('include_evidence_thumbnails') == 'on'
    report.include_osint_contacts = request.form.get('include_osint_contacts') == 'on'

    db.session.commit()

    flash('Informe actualizado exitosamente', 'success')
    return redirect(url_for('reports.report_detail', report_id=report_id))


@reports_bp.route('/report/<int:report_id>/generate', methods=['POST'])
@login_required
@audit_action('REPORT_GENERATE_PDF', 'report')
def generate_pdf(report_id):
    """Generate PDF for a report."""
    report = Report.query.get_or_404(report_id)

    # Check permissions
    if report.case.detective_id != current_user.id and not current_user.has_role('admin'):
        return jsonify({'error': 'Unauthorized'}), 403

    # Generate PDF
    result = ReportService.generate_pdf(report_id, current_user.id)

    if result['success']:
        flash('PDF generado exitosamente', 'success')
        return jsonify({
            'success': True,
            'message': 'PDF generado correctamente',
            'file_size': result['file_size'],
            'sha256': result['sha256']
        })
    else:
        flash(f'Error generando PDF: {result["error"]}', 'error')
        return jsonify({
            'success': False,
            'error': result['error']
        }), 500


@reports_bp.route('/report/<int:report_id>/download')
@login_required
@audit_action('REPORT_DOWNLOAD_PDF', 'report')
def download_pdf(report_id):
    """Download report PDF."""
    report = Report.query.get_or_404(report_id)

    # Check permissions
    if report.case.detective_id != current_user.id and not current_user.has_role('admin'):
        flash('No tienes permisos para descargar este informe', 'error')
        return redirect(url_for('cases.index'))

    # Check if PDF exists
    if not report.file_path or not os.path.exists(report.file_path):
        flash('El PDF no ha sido generado aún', 'error')
        return redirect(url_for('reports.report_detail', report_id=report_id))

    # Send file
    return send_file(
        report.file_path,
        as_attachment=True,
        download_name=report.get_file_name(),
        mimetype='application/pdf'
    )


@reports_bp.route('/report/<int:report_id>/export-json')
@login_required
@audit_action('REPORT_EXPORT_JSON', 'report')
def export_json(report_id):
    """Export report as JSON."""
    report = Report.query.get_or_404(report_id)

    # Check permissions
    if report.case.detective_id != current_user.id and not current_user.has_role('admin'):
        return jsonify({'error': 'Unauthorized'}), 403

    # Export as JSON
    result = ReportService.export_json(report_id, current_user.id)

    if result['success']:
        return jsonify(result['data'])
    else:
        return jsonify({'error': result['error']}), 500


@reports_bp.route('/report/<int:report_id>/delete', methods=['POST'])
@login_required
@audit_action('REPORT_DELETE', 'report')
def delete_report(report_id):
    """Delete a report."""
    report = Report.query.get_or_404(report_id)

    # Check permissions
    if report.case.detective_id != current_user.id and not current_user.has_role('admin'):
        flash('No tienes permisos para eliminar este informe', 'error')
        return redirect(url_for('cases.index'))

    case_id = report.case_id

    # Delete report
    success = ReportService.delete_report(report_id, current_user.id)

    if success:
        flash('Informe eliminado exitosamente', 'success')
    else:
        flash('Error al eliminar el informe', 'error')

    return redirect(url_for('reports.case_reports', case_id=case_id))
