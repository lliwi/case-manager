"""
Plugin routes for plugin management and execution.
"""
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app.blueprints.plugins import plugins_bp
from app.plugins import plugin_manager
from app.models.evidence import Evidence
from app.models.case import Case
from app.extensions import db
from app.utils.decorators import audit_action
import os


@plugins_bp.route('/')
@login_required
def index():
    """Display list of available plugins."""
    plugins = plugin_manager.get_all_plugins()

    forensic_plugins = [p for p in plugins if p.get('category') == 'forensic']
    osint_plugins = [p for p in plugins if p.get('category') == 'osint']

    return render_template(
        'plugins/index.html',
        forensic_plugins=forensic_plugins,
        osint_plugins=osint_plugins,
        total_plugins=len(plugins)
    )


@plugins_bp.route('/plugin/<plugin_name>')
@login_required
def plugin_detail(plugin_name):
    """Display plugin details."""
    plugin = plugin_manager.get_plugin_by_name(plugin_name)

    if not plugin:
        flash('Plugin no encontrado', 'error')
        return redirect(url_for('plugins.index'))

    plugin_info = plugin.get_info()

    return render_template(
        'plugins/detail.html',
        plugin=plugin,
        plugin_info=plugin_info
    )


@plugins_bp.route('/execute/forensic', methods=['GET', 'POST'])
@login_required
@audit_action('PLUGIN_EXECUTE_FORENSIC', 'plugin')
def execute_forensic():
    """Execute a forensic plugin on an evidence file."""
    if request.method == 'GET':
        # Get available evidence files and plugins
        cases = Case.query.filter_by(is_deleted=False).all()
        forensic_plugins = plugin_manager.get_forensic_plugins()

        plugins_info = [p.get_info() for p in forensic_plugins]

        return render_template(
            'plugins/execute_forensic.html',
            cases=cases,
            plugins=plugins_info
        )

    # POST - Execute plugin
    plugin_name = request.form.get('plugin_name')
    evidence_id = request.form.get('evidence_id')

    if not plugin_name or not evidence_id:
        flash('Plugin y evidencia son requeridos', 'error')
        return redirect(url_for('plugins.execute_forensic'))

    evidence = Evidence.query.get_or_404(evidence_id)

    # Check if user has access to this case
    if evidence.case.assigned_to_id != current_user.id and not current_user.has_role('admin'):
        flash('No tienes permisos para acceder a esta evidencia', 'error')
        return redirect(url_for('plugins.execute_forensic'))

    # Get file path (decrypt if needed)
    from app.services.evidence_service import EvidenceService
    file_path = EvidenceService.get_decrypted_file_path(evidence)

    # Execute plugin
    result = plugin_manager.execute_forensic_plugin(plugin_name, file_path)

    if result['success']:
        flash(f'Plugin {plugin_name} ejecutado exitosamente', 'success')
        return render_template(
            'plugins/result.html',
            plugin_name=plugin_name,
            evidence=evidence,
            result=result['result']
        )
    else:
        flash(f'Error ejecutando plugin: {result["error"]}', 'error')
        return redirect(url_for('plugins.execute_forensic'))


@plugins_bp.route('/execute/dni-validator', methods=['GET', 'POST'])
@login_required
@audit_action('PLUGIN_DNI_VALIDATOR', 'plugin')
def dni_validator():
    """DNI/NIE validator interface."""
    if request.method == 'GET':
        return render_template('plugins/dni_validator.html')

    # POST - Validate DNI/NIE
    identifier = request.form.get('identifier', '').strip()

    if not identifier:
        flash('Debe proporcionar un DNI/NIE', 'error')
        return redirect(url_for('plugins.dni_validator'))

    result = plugin_manager.validate_dni_nie(identifier)

    return render_template(
        'plugins/dni_validator.html',
        identifier=identifier,
        result=result
    )


@plugins_bp.route('/api/evidence/<int:evidence_id>/analyze/<plugin_name>', methods=['POST'])
@login_required
@audit_action('PLUGIN_API_ANALYZE_EVIDENCE', 'plugin')
def api_analyze_evidence(evidence_id, plugin_name):
    """
    API endpoint to analyze evidence with a plugin.

    Args:
        evidence_id: Evidence ID
        plugin_name: Plugin name to execute

    Returns:
        JSON response with analysis results
    """
    evidence = Evidence.query.get_or_404(evidence_id)

    # Check permissions
    if evidence.case.detective_id != current_user.id and not current_user.is_admin():
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        # Get decrypted file path
        file_path = evidence.get_decrypted_path()

        # Execute plugin
        result = plugin_manager.execute_forensic_plugin(plugin_name, file_path)

        return jsonify(result)

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@plugins_bp.route('/api/validate-dni', methods=['POST'])
@login_required
def api_validate_dni():
    """
    API endpoint to validate DNI/NIE.

    Returns:
        JSON response with validation result
    """
    data = request.get_json()
    identifier = data.get('identifier', '').strip()

    if not identifier:
        return jsonify({
            'valid': False,
            'error': 'Identifier required'
        }), 400

    result = plugin_manager.validate_dni_nie(identifier)
    return jsonify(result)


@plugins_bp.route('/case/<int:case_id>/analyze-evidence')
@login_required
def case_analyze_evidence(case_id):
    """Analyze all evidence in a case with plugins."""
    case = Case.query.get_or_404(case_id)

    # Check permissions
    if case.assigned_to_id != current_user.id and not current_user.has_role('admin'):
        flash('No tienes permisos para acceder a este caso', 'error')
        return redirect(url_for('cases.index'))

    # Get all evidence
    evidence_list = Evidence.query.filter_by(
        case_id=case_id,
        is_deleted=False
    ).all()

    # Get available plugins
    forensic_plugins = plugin_manager.get_forensic_plugins()
    plugins_info = [p.get_info() for p in forensic_plugins]

    return render_template(
        'plugins/case_analysis.html',
        case=case,
        evidence_list=evidence_list,
        plugins=plugins_info
    )
