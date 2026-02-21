"""
Plugin routes for plugin management and execution.
"""
from datetime import datetime, date, time
from flask import render_template, request, jsonify, flash, redirect, url_for, current_app, send_file, abort
from flask_login import login_required, current_user
from app.blueprints.plugins import plugins_bp
from app.plugins import plugin_manager
from app.models.evidence import Evidence
from app.models.case import Case
from app.extensions import db
from app.utils.decorators import audit_action
import os
import json
import mimetypes


def ensure_json_serializable(obj):
    """
    Ensure an object is JSON serializable by converting datetime objects to ISO format strings.
    This is a safety net to catch any datetime objects that weren't serialized by plugins.
    """
    if isinstance(obj, (datetime, date, time)):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: ensure_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [ensure_json_serializable(item) for item in obj]
    elif hasattr(obj, 'isoformat') and callable(obj.isoformat):
        try:
            return obj.isoformat()
        except Exception:
            return str(obj)
    else:
        return obj


def force_json_serialization(obj):
    """
    Force complete JSON serialization by using json.dumps/loads.
    This ensures the object is truly JSON-compatible before passing to SQLAlchemy.
    """
    # First pass: ensure all objects are serializable
    serialized = ensure_json_serializable(obj)

    # Second pass: force through JSON encoder/decoder to catch any remaining issues
    try:
        json_string = json.dumps(serialized, default=str)
        return json.loads(json_string)
    except (TypeError, ValueError) as e:
        # If still fails, convert entire object to string representation
        return {'error': f'Serialization failed: {str(e)}', 'raw_data': str(obj)}


@plugins_bp.route('/api/temp-image/<token>/<filename>')
@plugins_bp.route('/api/temp-image/<token>')
def serve_temp_image(token, filename=None):
    """
    Serve a temporarily accessible image for reverse image search.

    No authentication required — access is controlled exclusively by a
    one-time Redis token created by ReverseImageSearchService.  The token
    is consumed on the first (and only) request so subsequent calls return 404.

    The optional <filename> segment (e.g. photo.jpg) is present so that
    SerpAPI can detect the image type from the URL extension; it is not
    used for filesystem lookup (the token is the only key).
    """
    import redis as redis_lib

    try:
        r = redis_lib.from_url(current_app.config['REDIS_URL'])
        key = f'ris_token:{token}'

        # Atomic get-then-delete: one-time use
        pipe = r.pipeline()
        pipe.get(key)
        pipe.delete(key)
        results = pipe.execute()
        file_path_raw = results[0]

        if not file_path_raw:
            abort(404)

        file_path = file_path_raw.decode('utf-8') if isinstance(file_path_raw, bytes) else file_path_raw

        if not os.path.exists(file_path):
            abort(404)

        mime = mimetypes.guess_type(file_path)[0] or 'image/jpeg'
        return send_file(file_path, mimetype=mime)

    except Exception:
        abort(404)


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



@plugins_bp.route('/api/evidence/<int:evidence_id>/analyze/<plugin_name>', methods=['POST'])
@login_required
@audit_action('PLUGIN_API_ANALYZE_EVIDENCE', 'plugin')
def api_analyze_evidence(evidence_id, plugin_name):
    """
    API endpoint to analyze evidence with a plugin.

    Executes forensic plugin, stores results in database, and updates
    evidence metadata if relevant information is extracted (e.g., GPS coordinates).

    Args:
        evidence_id: Evidence ID
        plugin_name: Plugin name to execute

    Returns:
        JSON response with analysis results
    """
    from app.models.evidence_analysis import EvidenceAnalysis
    from app.extensions import db

    evidence = Evidence.query.get_or_404(evidence_id)

    # Check permissions
    if evidence.case.detective_id != current_user.id and not current_user.is_admin():
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        # Get decrypted file path
        file_path = evidence.get_decrypted_path()

        # Execute plugin
        result = plugin_manager.execute_forensic_plugin(plugin_name, file_path)

        # Get plugin info for version
        plugin_info = plugin_manager.get_plugin_by_name(plugin_name)
        plugin_version = plugin_info.get_info().get('version') if plugin_info else None

        # Check if analysis already exists for this evidence + plugin combination
        existing_analysis = EvidenceAnalysis.get_latest_by_plugin(evidence.id, plugin_name)

        if existing_analysis:
            # Update existing analysis
            existing_analysis.plugin_version = plugin_version
            existing_analysis.success = result.get('success', False)
            existing_analysis.result_data = force_json_serialization(result.get('result', {}))
            existing_analysis.error_message = result.get('error')
            existing_analysis.analyzed_by_id = current_user.id
            existing_analysis.analyzed_at = datetime.utcnow()
            analysis = existing_analysis
        else:
            # Create new analysis
            analysis = EvidenceAnalysis(
                evidence_id=evidence.id,
                plugin_name=plugin_name,
                plugin_version=plugin_version,
                success=result.get('success', False),
                result_data=force_json_serialization(result.get('result', {})),
                error_message=result.get('error'),
                analyzed_by_id=current_user.id
            )
            db.session.add(analysis)

        # Update evidence metadata if relevant data extracted
        if result.get('success') and plugin_name == 'exif_extractor':
            result_data = result.get('result', {})

            # Update GPS coordinates if found
            if result_data.get('gps'):
                gps_data = result_data['gps']
                evidence.geolocation_lat = gps_data.get('latitude')
                evidence.geolocation_lon = gps_data.get('longitude')

                # Log chain of custody update
                from app.models.evidence import ChainOfCustody
                ChainOfCustody.log(
                    action='METADATA_UPDATED',
                    evidence=evidence,
                    user=current_user,
                    notes=f'GPS coordinates extracted from EXIF: {gps_data.get("latitude")}, {gps_data.get("longitude")}'
                )

        db.session.commit()

        return jsonify(result)

    except Exception as e:
        db.session.rollback()
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
