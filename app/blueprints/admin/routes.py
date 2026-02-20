"""
Admin routes for system administration.
"""
from flask import render_template, request, jsonify, flash, redirect, url_for, send_file
from flask_login import login_required, current_user
from app.blueprints.admin import admin_bp
from app.models.user import User, Role
from app.models.audit import AuditLog
from app.models.case import Case
from app.models.evidence import Evidence
from app.models.report import Report
from app.utils.decorators import audit_action, require_role
from app.extensions import db
from datetime import datetime, timedelta
from sqlalchemy import func, desc
import csv
import io
import json
import os


@admin_bp.route('/')
@login_required
@require_role('admin')
@audit_action('ADMIN_DASHBOARD_VIEWED', 'admin')
def index():
    """Admin dashboard with system statistics."""
    # Get system statistics
    from app.models.case import CaseStatus
    stats = {
        'total_users': User.query.count(),
        'active_users': User.query.filter_by(is_active=True).count(),
        'total_cases': Case.query.filter_by(is_deleted=False).count(),
        'active_cases': Case.query.filter(
            Case.is_deleted == False,
            Case.status == CaseStatus.EN_INVESTIGACION
        ).count(),
        'total_evidence': Evidence.query.filter_by(is_deleted=False).count(),
        'total_reports': Report.query.filter_by(is_deleted=False).count(),
        'total_audit_logs': AuditLog.query.count()
    }

    # Recent audit logs
    recent_logs = AuditLog.query.order_by(desc(AuditLog.timestamp)).limit(10).all()

    # User activity in last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    active_users_30d = db.session.query(func.count(func.distinct(AuditLog.user_id))).filter(
        AuditLog.timestamp >= thirty_days_ago
    ).scalar()

    stats['active_users_30d'] = active_users_30d

    return render_template(
        'admin/index.html',
        stats=stats,
        recent_logs=recent_logs
    )


# ============================================================================
# USER MANAGEMENT
# ============================================================================

@admin_bp.route('/users')
@login_required
@require_role('admin')
@audit_action('ADMIN_USERS_LIST_VIEWED', 'admin')
def users():
    """List all users."""
    users = User.query.order_by(User.created_at.desc()).all()

    return render_template(
        'admin/users.html',
        users=users
    )


@admin_bp.route('/users/<int:user_id>')
@login_required
@require_role('admin')
@audit_action('ADMIN_USER_VIEWED', 'admin')
def user_detail(user_id):
    """View user details."""
    user = User.query.get_or_404(user_id)

    # Get user's cases
    user_cases = Case.query.filter_by(
        detective_id=user_id,
        is_deleted=False
    ).order_by(desc(Case.created_at)).limit(10).all()

    # Get user's recent activity
    recent_activity = AuditLog.query.filter_by(user_id=user_id).order_by(
        desc(AuditLog.timestamp)
    ).limit(20).all()

    return render_template(
        'admin/user_detail.html',
        user=user,
        user_cases=user_cases,
        recent_activity=recent_activity
    )


@admin_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@require_role('admin')
@audit_action('ADMIN_USER_CREATE', 'admin')
def create_user():
    """Create a new user."""
    if request.method == 'GET':
        roles = Role.query.all()
        return render_template('admin/create_user.html', roles=roles)

    # POST - Create user
    email = request.form.get('email')
    nombre = request.form.get('nombre')
    apellidos = request.form.get('apellidos')
    tip_number = request.form.get('tip_number')
    despacho = request.form.get('despacho')
    telefono = request.form.get('telefono')
    password = request.form.get('password')
    role_ids = request.form.getlist('roles')

    # Validate
    if User.query.filter_by(email=email).first():
        flash('El email ya está registrado', 'error')
        return redirect(url_for('admin.create_user'))

    # Create user
    user = User(
        email=email,
        nombre=nombre,
        apellidos=apellidos,
        tip_number=tip_number,
        despacho=despacho,
        telefono=telefono,
        is_active=True,
        email_verified=True
    )
    user.set_password(password)

    # Assign roles
    for role_id in role_ids:
        role = Role.query.get(role_id)
        if role:
            user.roles.append(role)

    db.session.add(user)
    db.session.commit()

    flash(f'Usuario {email} creado exitosamente', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@require_role('admin')
@audit_action('ADMIN_USER_EDIT', 'admin')
def edit_user(user_id):
    """Edit an existing user."""
    user = User.query.get_or_404(user_id)
    roles = Role.query.all()

    if request.method == 'GET':
        return render_template('admin/edit_user.html', user=user, roles=roles)

    # POST - Update user
    email = request.form.get('email')
    nombre = request.form.get('nombre')
    apellidos = request.form.get('apellidos')
    tip_number = request.form.get('tip_number')
    despacho = request.form.get('despacho')
    telefono = request.form.get('telefono')
    role_ids = request.form.getlist('roles')

    # Validate email uniqueness (excluding current user)
    existing_user = User.query.filter(
        User.email == email,
        User.id != user_id
    ).first()
    if existing_user:
        flash('El email ya está registrado por otro usuario', 'error')
        return redirect(url_for('admin.edit_user', user_id=user_id))

    # Update user fields
    user.email = email
    user.nombre = nombre
    user.apellidos = apellidos
    user.tip_number = tip_number
    user.despacho = despacho
    user.telefono = telefono

    # Update roles
    user.roles = []
    for role_id in role_ids:
        role = Role.query.get(role_id)
        if role:
            user.roles.append(role)

    db.session.commit()

    flash(f'Usuario {email} actualizado exitosamente', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))


@admin_bp.route('/users/<int:user_id>/toggle-status', methods=['POST'])
@login_required
@require_role('admin')
@audit_action('ADMIN_USER_TOGGLE_STATUS', 'admin')
def toggle_user_status(user_id):
    """Activate or deactivate a user."""
    user = User.query.get_or_404(user_id)

    # Cannot deactivate yourself
    if user.id == current_user.id:
        flash('No puedes desactivar tu propia cuenta', 'error')
        return redirect(url_for('admin.users'))

    user.is_active = not user.is_active
    db.session.commit()

    status = 'activado' if user.is_active else 'desactivado'
    flash(f'Usuario {user.email} {status} exitosamente', 'success')

    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
@login_required
@require_role('admin')
@audit_action('ADMIN_USER_RESET_PASSWORD', 'admin')
def reset_user_password(user_id):
    """Reset user password."""
    user = User.query.get_or_404(user_id)

    new_password = request.form.get('new_password')
    if not new_password or len(new_password) < 8:
        flash('La contraseña debe tener al menos 8 caracteres', 'error')
        return redirect(url_for('admin.user_detail', user_id=user_id))

    user.set_password(new_password)
    db.session.commit()

    flash(f'Contraseña de {user.email} restablecida exitosamente', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))


@admin_bp.route('/users/<int:user_id>/disable-mfa', methods=['POST'])
@login_required
@require_role('admin')
@audit_action('ADMIN_USER_DISABLE_MFA', 'admin')
def disable_user_mfa(user_id):
    """Disable MFA for a user so they can set it up again."""
    user = User.query.get_or_404(user_id)

    if not user.mfa_enabled:
        flash(f'El usuario {user.email} no tiene MFA activado', 'warning')
        return redirect(url_for('admin.user_detail', user_id=user_id))

    # Disable MFA and clear secret
    user.mfa_enabled = False
    user.mfa_secret = None
    db.session.commit()

    flash(f'MFA desactivado para {user.email}. El usuario puede configurarlo de nuevo.', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))


# ============================================================================
# AUDIT LOG VIEWER
# ============================================================================

@admin_bp.route('/audit-logs')
@login_required
@require_role('admin')
@audit_action('ADMIN_AUDIT_LOGS_VIEWED', 'admin')
def audit_logs():
    """View audit logs with filtering."""
    # Get filter parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    action = request.args.get('action')
    resource_type = request.args.get('resource_type')
    user_id = request.args.get('user_id', type=int)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    # Build query
    query = AuditLog.query

    if action:
        query = query.filter(AuditLog.action == action)

    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)

    if user_id:
        query = query.filter(AuditLog.user_id == user_id)

    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(AuditLog.timestamp >= date_from_obj)
        except ValueError:
            pass

    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            # Add 1 day to include the entire day
            date_to_obj = date_to_obj + timedelta(days=1)
            query = query.filter(AuditLog.timestamp < date_to_obj)
        except ValueError:
            pass

    # Order by most recent
    query = query.order_by(desc(AuditLog.timestamp))

    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # Get unique actions and resource types for filters
    unique_actions = db.session.query(AuditLog.action).distinct().order_by(AuditLog.action).all()
    unique_actions = [a[0] for a in unique_actions if a[0]]

    unique_resource_types = db.session.query(AuditLog.resource_type).distinct().order_by(
        AuditLog.resource_type
    ).all()
    unique_resource_types = [r[0] for r in unique_resource_types if r[0]]

    # Get all users for filter
    users = User.query.order_by(User.nombre).all()

    return render_template(
        'admin/audit_logs.html',
        pagination=pagination,
        unique_actions=unique_actions,
        unique_resource_types=unique_resource_types,
        users=users,
        filters={
            'action': action,
            'resource_type': resource_type,
            'user_id': user_id,
            'date_from': date_from,
            'date_to': date_to
        }
    )


@admin_bp.route('/audit-logs/<int:log_id>')
@login_required
@require_role('admin')
def audit_log_detail(log_id):
    """View audit log details."""
    log = AuditLog.query.get_or_404(log_id)

    return render_template(
        'admin/audit_log_detail.html',
        log=log
    )


@admin_bp.route('/audit-logs/export')
@login_required
@require_role('admin')
@audit_action('ADMIN_AUDIT_LOGS_EXPORT', 'admin')
def export_audit_logs():
    """Export audit logs to CSV."""
    # Get filter parameters (same as audit_logs route)
    action = request.args.get('action')
    resource_type = request.args.get('resource_type')
    user_id = request.args.get('user_id', type=int)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    # Build query
    query = AuditLog.query

    if action:
        query = query.filter(AuditLog.action == action)

    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)

    if user_id:
        query = query.filter(AuditLog.user_id == user_id)

    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(AuditLog.timestamp >= date_from_obj)
        except ValueError:
            pass

    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            date_to_obj = date_to_obj + timedelta(days=1)
            query = query.filter(AuditLog.timestamp < date_to_obj)
        except ValueError:
            pass

    # Order by most recent
    query = query.order_by(desc(AuditLog.timestamp))

    # Limit to prevent huge exports
    logs = query.limit(10000).all()

    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        'ID', 'Timestamp', 'Action', 'Resource Type', 'Resource ID',
        'User', 'IP Address', 'User Agent', 'Extra Data'
    ])

    # Data
    for log in logs:
        writer.writerow([
            log.id,
            log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            log.action,
            log.resource_type or '',
            log.resource_id or '',
            log.user.email if log.user else 'System',
            log.ip_address or '',
            log.user_agent or '',
            json.dumps(log.extra_data) if log.extra_data else ''
        ])

    # Create response
    output.seek(0)
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    filename = f'audit_logs_{timestamp}.csv'

    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename
    )


# ============================================================================
# SYSTEM SETTINGS
# ============================================================================

@admin_bp.route('/settings')
@login_required
@require_role('admin')
@audit_action('ADMIN_SETTINGS_VIEWED', 'admin')
def settings():
    """View system settings."""
    # Get system info
    import os
    import sys
    from flask import __version__ as flask_version

    system_info = {
        'python_version': sys.version,
        'flask_version': flask_version,
        'environment': os.getenv('FLASK_ENV', 'production'),
        'database_url': os.getenv('DATABASE_URL', 'Not configured')[:50] + '...',
    }

    return render_template(
        'admin/settings.html',
        system_info=system_info
    )


# ============================================================================
# ROLE MANAGEMENT
# ============================================================================

@admin_bp.route('/roles')
@login_required
@require_role('admin')
@audit_action('ADMIN_ROLES_VIEWED', 'admin')
def roles():
    """List all roles."""
    all_roles = Role.query.all()

    # Get user count for each role
    role_stats = []
    for role in all_roles:
        user_count = db.session.query(func.count(User.id)).join(
            User.roles
        ).filter(Role.id == role.id).scalar()

        role_stats.append({
            'role': role,
            'user_count': user_count
        })

    return render_template(
        'admin/roles.html',
        role_stats=role_stats
    )


@admin_bp.route('/users/<int:user_id>/roles', methods=['POST'])
@login_required
@require_role('admin')
@audit_action('ADMIN_USER_ROLES_UPDATE', 'admin')
def update_user_roles(user_id):
    """Update user roles."""
    user = User.query.get_or_404(user_id)

    role_ids = request.form.getlist('roles')

    # Clear existing roles
    user.roles = []

    # Add new roles
    for role_id in role_ids:
        role = Role.query.get(role_id)
        if role:
            user.roles.append(role)

    db.session.commit()

    flash(f'Roles de {user.email} actualizados exitosamente', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))


# ============================================================================
# LEGITIMACY TYPES MANAGEMENT
# ============================================================================

@admin_bp.route('/legitimacy-types')
@login_required
@require_role('admin')
@audit_action('ADMIN_LEGITIMACY_TYPES_VIEWED', 'admin')
def legitimacy_types():
    """View all legitimacy types with usage statistics."""
    from app.models.case import LegitimacyType
    from app.models.legitimacy_type_custom import LegitimacyTypeCustom

    # Get all legitimacy types from enum
    all_types = list(LegitimacyType)

    # Calculate usage statistics for each type
    type_stats = []
    for leg_type in all_types:
        case_count = Case.query.filter(
            Case.legitimacy_type == leg_type,
            Case.is_deleted == False
        ).count()

        # Get recent cases using this type
        recent_cases = Case.query.filter(
            Case.legitimacy_type == leg_type,
            Case.is_deleted == False
        ).order_by(desc(Case.created_at)).limit(5).all()

        type_stats.append({
            'type': leg_type,
            'name': leg_type.name,
            'value': leg_type.value,
            'case_count': case_count,
            'recent_cases': recent_cases,
            'is_custom': False,
            'is_deletable': False
        })

    # Get custom types
    custom_types = LegitimacyTypeCustom.query.filter_by(is_deleted=False).all()
    for custom_type in custom_types:
        case_count = Case.query.filter(
            Case.legitimacy_type_custom_id == custom_type.id,
            Case.is_deleted == False
        ).count()

        recent_cases = Case.query.filter(
            Case.legitimacy_type_custom_id == custom_type.id,
            Case.is_deleted == False
        ).order_by(desc(Case.created_at)).limit(5).all()

        type_stats.append({
            'type': custom_type,
            'name': custom_type.name,
            'value': custom_type.name,
            'description': custom_type.description,
            'legal_reference': custom_type.legal_reference,
            'case_count': case_count,
            'recent_cases': recent_cases,
            'is_custom': True,
            'is_deletable': case_count == 0,
            'custom_id': custom_type.id
        })

    # Sort by usage count (most used first)
    type_stats.sort(key=lambda x: x['case_count'], reverse=True)

    return render_template(
        'admin/legitimacy_types.html',
        type_stats=type_stats,
        total_cases=Case.query.filter_by(is_deleted=False).count()
    )


@admin_bp.route('/legitimacy-types/create', methods=['GET', 'POST'])
@login_required
@require_role('admin')
@audit_action('ADMIN_LEGITIMACY_TYPE_CREATE', 'admin')
def create_legitimacy_type():
    """Create a new custom legitimacy type."""
    from app.blueprints.admin.forms import LegitimacyTypeCustomForm
    from app.models.legitimacy_type_custom import LegitimacyTypeCustom

    form = LegitimacyTypeCustomForm()

    if form.validate_on_submit():
        # Check if name already exists
        existing = LegitimacyTypeCustom.query.filter_by(
            name=form.name.data,
            is_deleted=False
        ).first()

        if existing:
            flash(f'Ya existe un tipo con el nombre "{form.name.data}"', 'danger')
            return render_template('admin/legitimacy_type_form.html', form=form, editing=False)

        # Create new custom type
        custom_type = LegitimacyTypeCustom(
            name=form.name.data,
            description=form.description.data,
            legal_reference=form.legal_reference.data,
            is_active=form.is_active.data,
            created_by_id=current_user.id
        )

        db.session.add(custom_type)
        db.session.commit()

        flash(f'Tipo de legitimidad "{custom_type.name}" creado exitosamente', 'success')
        return redirect(url_for('admin.legitimacy_types'))

    return render_template('admin/legitimacy_type_form.html', form=form, editing=False)



@admin_bp.route('/legitimacy-types/<int:type_id>/edit', methods=['GET', 'POST'])
@login_required
@require_role('admin')
@audit_action('ADMIN_LEGITIMACY_TYPE_EDIT', 'admin')
def edit_legitimacy_type(type_id):
    """Edit a custom legitimacy type."""
    from app.blueprints.admin.forms import LegitimacyTypeCustomForm
    from app.models.legitimacy_type_custom import LegitimacyTypeCustom

    custom_type = LegitimacyTypeCustom.query.get_or_404(type_id)

    form = LegitimacyTypeCustomForm(obj=custom_type)

    if form.validate_on_submit():
        # Check if name already exists (excluding current record)
        existing = LegitimacyTypeCustom.query.filter(
            LegitimacyTypeCustom.name == form.name.data,
            LegitimacyTypeCustom.id != type_id,
            LegitimacyTypeCustom.is_deleted == False
        ).first()

        if existing:
            flash(f'Ya existe un tipo con el nombre "{form.name.data}"', 'danger')
            return render_template('admin/legitimacy_type_form.html', 
                                   form=form, editing=True, custom_type=custom_type)

        # Update custom type
        custom_type.name = form.name.data
        custom_type.description = form.description.data
        custom_type.legal_reference = form.legal_reference.data
        custom_type.is_active = form.is_active.data
        custom_type.updated_at = datetime.utcnow()

        db.session.commit()

        flash(f'Tipo de legitimidad "{custom_type.name}" actualizado exitosamente', 'success')
        return redirect(url_for('admin.legitimacy_types'))

    return render_template('admin/legitimacy_type_form.html', 
                           form=form, editing=True, custom_type=custom_type)

@admin_bp.route('/legitimacy-types/<int:type_id>/delete', methods=['POST'])
@login_required
@require_role('admin')
@audit_action('ADMIN_LEGITIMACY_TYPE_DELETE', 'admin')
def delete_legitimacy_type(type_id):
    """Delete a custom legitimacy type."""
    from app.models.legitimacy_type_custom import LegitimacyTypeCustom

    custom_type = LegitimacyTypeCustom.query.get_or_404(type_id)

    # Check if type is in use
    case_count = Case.query.filter(
        Case.legitimacy_type_custom_id == custom_type.id,
        Case.is_deleted == False
    ).count()

    if case_count > 0:
        flash(
            f'No se puede eliminar el tipo "{custom_type.name}" porque está siendo '
            f'utilizado por {case_count} caso(s) activo(s)',
            'danger'
        )
        return redirect(url_for('admin.legitimacy_types'))

    # Soft delete
    try:
        custom_type.soft_delete(current_user)
        flash(f'Tipo de legitimidad "{custom_type.name}" eliminado exitosamente', 'success')
    except ValueError as e:
        flash(str(e), 'danger')

    return redirect(url_for('admin.legitimacy_types'))


# ============================================================================
# RELATIONSHIP TYPES MANAGEMENT
# ============================================================================

@admin_bp.route('/relationship-types')
@login_required
@require_role('admin')
@audit_action('ADMIN_RELATIONSHIP_TYPES_VIEWED', 'admin')
def relationship_types():
    """View all relationship types with statistics."""
    from app.models.graph import RelationshipType
    from app.models.relationship_type_custom import RelationshipTypeCustom

    # Get all base relationship types from enum
    base_types = list(RelationshipType)

    # Build type stats for base types
    type_stats = []
    for rel_type in base_types:
        type_stats.append({
            'name': rel_type.value,
            'label': rel_type.value.replace('_', ' ').title(),
            'description': f'Tipo de relación base: {rel_type.value}',
            'is_custom': False,
            'is_deletable': False,
            'is_active': True
        })

    # Get custom types
    custom_types = RelationshipTypeCustom.query.filter_by(is_deleted=False).all()
    for custom_type in custom_types:
        type_stats.append({
            'name': custom_type.name,
            'label': custom_type.label,
            'description': custom_type.description,
            'is_custom': True,
            'is_deletable': True,
            'is_active': custom_type.is_active,
            'custom_id': custom_type.id,
            'created_at': custom_type.created_at,
            'created_by': custom_type.created_by.email if custom_type.created_by else 'Sistema'
        })

    # Sort: base types first, then custom types by name
    type_stats.sort(key=lambda x: (x['is_custom'], x['name']))

    return render_template(
        'admin/relationship_types.html',
        type_stats=type_stats,
        total_base_types=len(base_types),
        total_custom_types=len(custom_types)
    )


@admin_bp.route('/relationship-types/create', methods=['GET', 'POST'])
@login_required
@require_role('admin')
@audit_action('ADMIN_RELATIONSHIP_TYPE_CREATE', 'admin')
def create_relationship_type():
    """Create a new custom relationship type."""
    from app.blueprints.admin.forms import RelationshipTypeCustomForm
    from app.models.relationship_type_custom import RelationshipTypeCustom

    form = RelationshipTypeCustomForm()

    if form.validate_on_submit():
        # Check if name already exists
        existing = RelationshipTypeCustom.query.filter_by(
            name=form.name.data.upper(),
            is_deleted=False
        ).first()

        if existing:
            flash(f'Ya existe un tipo con el nombre "{form.name.data}"', 'danger')
            return render_template('admin/relationship_type_form.html', form=form, editing=False)

        # Create new custom type
        custom_type = RelationshipTypeCustom(
            name=form.name.data.upper(),  # Store in uppercase like enum values
            label=form.label.data,
            description=form.description.data,
            is_active=form.is_active.data,
            created_by_id=current_user.id
        )

        db.session.add(custom_type)
        db.session.commit()

        flash(f'Tipo de relación "{custom_type.label}" creado exitosamente', 'success')
        return redirect(url_for('admin.relationship_types'))

    return render_template('admin/relationship_type_form.html', form=form, editing=False)


@admin_bp.route('/relationship-types/<int:type_id>/delete', methods=['POST'])
@login_required
@require_role('admin')
@audit_action('ADMIN_RELATIONSHIP_TYPE_DELETE', 'admin')
def delete_relationship_type(type_id):
    """Delete a custom relationship type."""
    from app.models.relationship_type_custom import RelationshipTypeCustom

    custom_type = RelationshipTypeCustom.query.get_or_404(type_id)

    # Soft delete
    try:
        custom_type.soft_delete(current_user)
        flash(f'Tipo de relación "{custom_type.label}" eliminado exitosamente', 'success')
    except Exception as e:
        flash(f'Error al eliminar: {str(e)}', 'danger')

    return redirect(url_for('admin.relationship_types'))


@admin_bp.route('/relationship-types/<int:type_id>/toggle', methods=['POST'])
@login_required
@require_role('admin')
@audit_action('ADMIN_RELATIONSHIP_TYPE_TOGGLE', 'admin')
def toggle_relationship_type(type_id):
    """Toggle active status of a custom relationship type."""
    from app.models.relationship_type_custom import RelationshipTypeCustom

    custom_type = RelationshipTypeCustom.query.get_or_404(type_id)

    custom_type.is_active = not custom_type.is_active
    custom_type.updated_at = datetime.utcnow()
    db.session.commit()

    status = 'activado' if custom_type.is_active else 'desactivado'
    flash(f'Tipo de relación "{custom_type.label}" {status} exitosamente', 'success')

    return redirect(url_for('admin.relationship_types'))


@admin_bp.route('/relationship-types/<int:type_id>/edit', methods=['GET', 'POST'])
@login_required
@require_role('admin')
@audit_action('ADMIN_RELATIONSHIP_TYPE_EDIT', 'admin')
def edit_relationship_type(type_id):
    """Edit a custom relationship type."""
    from app.blueprints.admin.forms import RelationshipTypeCustomForm
    from app.models.relationship_type_custom import RelationshipTypeCustom

    custom_type = RelationshipTypeCustom.query.get_or_404(type_id)

    form = RelationshipTypeCustomForm(obj=custom_type)

    if form.validate_on_submit():
        # Check if name already exists (excluding current record)
        existing = RelationshipTypeCustom.query.filter(
            RelationshipTypeCustom.name == form.name.data.upper(),
            RelationshipTypeCustom.id != type_id,
            RelationshipTypeCustom.is_deleted == False
        ).first()

        if existing:
            flash(f'Ya existe un tipo con el nombre "{form.name.data}"', 'danger')
            return render_template('admin/relationship_type_form.html', 
                                   form=form, editing=True, custom_type=custom_type)

        # Update custom type
        custom_type.name = form.name.data.upper()
        custom_type.label = form.label.data
        custom_type.description = form.description.data
        custom_type.is_active = form.is_active.data
        custom_type.updated_at = datetime.utcnow()

        db.session.commit()

        flash(f'Tipo de relación "{custom_type.label}" actualizado exitosamente', 'success')
        return redirect(url_for('admin.relationship_types'))

    return render_template('admin/relationship_type_form.html',
                           form=form, editing=True, custom_type=custom_type)


# ============================================================================
# API KEY MANAGEMENT
# ============================================================================

@admin_bp.route('/api-keys')
@login_required
@require_role('admin')
@audit_action('ADMIN_API_KEYS_LIST_VIEWED', 'admin')
def api_keys():
    """List all API keys."""
    from app.models.api_key import ApiKey

    # Get all API keys (excluding soft deleted)
    keys = ApiKey.query.filter_by(is_deleted=False).order_by(
        desc(ApiKey.created_at)
    ).all()

    # Group by service
    keys_by_service = {}
    for key in keys:
        if key.service_name not in keys_by_service:
            keys_by_service[key.service_name] = []
        keys_by_service[key.service_name].append(key)

    return render_template(
        'admin/api_keys.html',
        keys=keys,
        keys_by_service=keys_by_service,
        total_keys=len(keys)
    )


@admin_bp.route('/api-keys/create', methods=['GET', 'POST'])
@login_required
@require_role('admin')
@audit_action('ADMIN_API_KEY_CREATE', 'admin')
def create_api_key():
    """Create a new API key."""
    from app.blueprints.admin.forms import ApiKeyForm
    from app.models.api_key import ApiKey

    form = ApiKeyForm()

    if form.validate_on_submit():
        # Check if key name already exists for this service
        existing = ApiKey.query.filter_by(
            service_name=form.service_name.data,
            key_name=form.key_name.data,
            is_deleted=False
        ).first()

        if existing:
            flash(f'Ya existe una API Key con el nombre "{form.key_name.data}" para este servicio', 'danger')
            return render_template('admin/api_key_form.html', form=form, editing=False)

        # Create new API key
        try:
            api_key = ApiKey(
                service_name=form.service_name.data,
                key_name=form.key_name.data,
                api_key=form.api_key.data,
                description=form.description.data,
                created_by_id=current_user.id
            )
            api_key.is_active = form.is_active.data

            db.session.add(api_key)
            db.session.commit()

            flash(f'API Key "{api_key.key_name}" creada exitosamente', 'success')
            return redirect(url_for('admin.api_keys'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear la API Key: {str(e)}', 'danger')
            return render_template('admin/api_key_form.html', form=form, editing=False)

    return render_template('admin/api_key_form.html', form=form, editing=False)


@admin_bp.route('/api-keys/<int:key_id>')
@login_required
@require_role('admin')
@audit_action('ADMIN_API_KEY_VIEWED', 'admin')
def api_key_detail(key_id):
    """View API key details."""
    from app.models.api_key import ApiKey

    api_key = ApiKey.query.get_or_404(key_id)

    if api_key.is_deleted:
        flash('Esta API Key ha sido eliminada', 'warning')
        return redirect(url_for('admin.api_keys'))

    return render_template(
        'admin/api_key_detail.html',
        api_key=api_key
    )


@admin_bp.route('/api-keys/<int:key_id>/edit', methods=['GET', 'POST'])
@login_required
@require_role('admin')
@audit_action('ADMIN_API_KEY_EDIT', 'admin')
def edit_api_key(key_id):
    """Edit an API key."""
    from app.blueprints.admin.forms import ApiKeyForm
    from app.models.api_key import ApiKey

    api_key = ApiKey.query.get_or_404(key_id)

    if api_key.is_deleted:
        flash('Esta API Key ha sido eliminada', 'warning')
        return redirect(url_for('admin.api_keys'))

    form = ApiKeyForm()

    # Pre-populate form on GET
    if request.method == 'GET':
        form.service_name.data = api_key.service_name
        form.key_name.data = api_key.key_name
        form.description.data = api_key.description
        form.is_active.data = api_key.is_active
        # Don't populate api_key field for security

    if form.validate_on_submit():
        # Check if key name already exists (excluding current record)
        existing = ApiKey.query.filter(
            ApiKey.service_name == form.service_name.data,
            ApiKey.key_name == form.key_name.data,
            ApiKey.id != key_id,
            ApiKey.is_deleted == False
        ).first()

        if existing:
            flash(f'Ya existe una API Key con el nombre "{form.key_name.data}" para este servicio', 'danger')
            return render_template('admin/api_key_form.html',
                                   form=form, editing=True, api_key=api_key)

        # Update API key
        try:
            api_key.service_name = form.service_name.data
            api_key.key_name = form.key_name.data
            api_key.description = form.description.data
            api_key.is_active = form.is_active.data

            # Only update the actual API key if a new one was provided
            if form.api_key.data:
                api_key.set_api_key(form.api_key.data)

            api_key.updated_at = datetime.utcnow()

            db.session.commit()

            flash(f'API Key "{api_key.key_name}" actualizada exitosamente', 'success')
            return redirect(url_for('admin.api_keys'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar la API Key: {str(e)}', 'danger')
            return render_template('admin/api_key_form.html',
                                   form=form, editing=True, api_key=api_key)

    return render_template('admin/api_key_form.html',
                           form=form, editing=True, api_key=api_key)


@admin_bp.route('/api-keys/<int:key_id>/toggle', methods=['POST'])
@login_required
@require_role('admin')
@audit_action('ADMIN_API_KEY_TOGGLE', 'admin')
def toggle_api_key(key_id):
    """Toggle active status of an API key."""
    from app.models.api_key import ApiKey

    api_key = ApiKey.query.get_or_404(key_id)

    if api_key.is_deleted:
        flash('Esta API Key ha sido eliminada', 'warning')
        return redirect(url_for('admin.api_keys'))

    api_key.is_active = not api_key.is_active
    api_key.updated_at = datetime.utcnow()
    db.session.commit()

    status = 'activada' if api_key.is_active else 'desactivada'
    flash(f'API Key "{api_key.key_name}" {status} exitosamente', 'success')

    return redirect(url_for('admin.api_keys'))


@admin_bp.route('/api-keys/<int:key_id>/delete', methods=['POST'])
@login_required
@require_role('admin')
@audit_action('ADMIN_API_KEY_DELETE', 'admin')
def delete_api_key(key_id):
    """Delete an API key."""
    from app.models.api_key import ApiKey

    api_key = ApiKey.query.get_or_404(key_id)

    if api_key.is_deleted:
        flash('Esta API Key ya ha sido eliminada', 'warning')
        return redirect(url_for('admin.api_keys'))

    # Soft delete
    try:
        api_key.soft_delete(current_user)
        flash(f'API Key "{api_key.key_name}" eliminada exitosamente', 'success')
    except Exception as e:
        flash(f'Error al eliminar: {str(e)}', 'danger')

    return redirect(url_for('admin.api_keys'))


# ============================================================================
# OSINT CONTACT TYPE CONFIGURATION
# ============================================================================

@admin_bp.route('/osint-contact-types')
@login_required
@require_role('admin')
@audit_action('ADMIN_OSINT_CONTACT_TYPES_VIEWED', 'admin')
def osint_contact_types():
    """View and manage OSINT contact type configurations."""
    from app.models.osint_contact_type_config import OSINTContactTypeConfig
    from app.models.osint_contact import OSINTContact

    configs = OSINTContactTypeConfig.query.order_by(
        OSINTContactTypeConfig.sort_order
    ).all()

    # Count contacts per type
    contact_counts = {}
    for config in configs:
        count = OSINTContact.query.filter_by(
            contact_type=config.type_key,
            is_deleted=False
        ).count()
        contact_counts[config.type_key] = count

    return render_template(
        'admin/osint_contact_types.html',
        configs=configs,
        contact_counts=contact_counts,
    )


@admin_bp.route('/osint-contact-types/create', methods=['GET', 'POST'])
@login_required
@require_role('admin')
@audit_action('ADMIN_OSINT_CONTACT_TYPE_CREATE', 'admin')
def create_osint_contact_type():
    """Create a new custom OSINT contact type."""
    from app.blueprints.admin.forms import OSINTContactTypeConfigForm
    from app.models.osint_contact_type_config import OSINTContactTypeConfig

    form = OSINTContactTypeConfigForm()

    if form.validate_on_submit():
        type_key = form.type_key.data.strip().lower()

        existing = OSINTContactTypeConfig.query.filter_by(type_key=type_key).first()
        if existing:
            flash(f'Ya existe un tipo con la clave "{type_key}"', 'danger')
            return render_template('admin/osint_contact_type_form.html',
                                   form=form, config=None, creating=True)

        config = OSINTContactTypeConfig(
            type_key=type_key,
            display_name=form.display_name.data,
            description=form.description.data,
            icon_class=form.icon_class.data or 'bi-info-circle',
            color=form.color.data,
            sort_order=form.sort_order.data,
            is_active=form.is_active.data,
            is_builtin=False,
            created_by_id=current_user.id,
        )
        db.session.add(config)
        db.session.commit()

        flash(f'Tipo de contacto "{config.display_name}" creado exitosamente', 'success')
        return redirect(url_for('admin.osint_contact_types'))

    return render_template('admin/osint_contact_type_form.html',
                           form=form, config=None, creating=True)


@admin_bp.route('/osint-contact-types/<int:config_id>/edit', methods=['GET', 'POST'])
@login_required
@require_role('admin')
@audit_action('ADMIN_OSINT_CONTACT_TYPE_EDIT', 'admin')
def edit_osint_contact_type(config_id):
    """Edit an OSINT contact type configuration."""
    from app.blueprints.admin.forms import OSINTContactTypeConfigForm
    from app.models.osint_contact_type_config import OSINTContactTypeConfig

    config = OSINTContactTypeConfig.query.get_or_404(config_id)
    form = OSINTContactTypeConfigForm(obj=config)

    if form.validate_on_submit():
        config.display_name = form.display_name.data
        config.description = form.description.data
        config.icon_class = form.icon_class.data or 'bi-info-circle'
        config.color = form.color.data
        config.sort_order = form.sort_order.data
        config.is_active = form.is_active.data
        config.updated_at = datetime.utcnow()

        db.session.commit()
        flash(f'Tipo de contacto "{config.display_name}" actualizado exitosamente', 'success')
        return redirect(url_for('admin.osint_contact_types'))

    return render_template(
        'admin/osint_contact_type_form.html',
        form=form,
        config=config,
        creating=False,
    )


@admin_bp.route('/osint-contact-types/<int:config_id>/toggle', methods=['POST'])
@login_required
@require_role('admin')
@audit_action('ADMIN_OSINT_CONTACT_TYPE_TOGGLE', 'admin')
def toggle_osint_contact_type(config_id):
    """Toggle active/inactive status of an OSINT contact type."""
    from app.models.osint_contact_type_config import OSINTContactTypeConfig

    config = OSINTContactTypeConfig.query.get_or_404(config_id)
    config.is_active = not config.is_active
    config.updated_at = datetime.utcnow()
    db.session.commit()

    status = 'activado' if config.is_active else 'desactivado'
    flash(f'Tipo de contacto "{config.display_name}" {status} exitosamente', 'success')
    return redirect(url_for('admin.osint_contact_types'))


@admin_bp.route('/osint-contact-types/<int:config_id>/delete', methods=['POST'])
@login_required
@require_role('admin')
@audit_action('ADMIN_OSINT_CONTACT_TYPE_DELETE', 'admin')
def delete_osint_contact_type(config_id):
    """Delete a custom (non-builtin) OSINT contact type."""
    from app.models.osint_contact_type_config import OSINTContactTypeConfig

    config = OSINTContactTypeConfig.query.get_or_404(config_id)

    if config.is_builtin:
        flash('Los tipos integrados no se pueden eliminar.', 'danger')
        return redirect(url_for('admin.osint_contact_types'))

    count = config.contact_count()
    if count > 0:
        flash(
            f'No se puede eliminar "{config.display_name}": '
            f'hay {count} contacto(s) que usan este tipo.',
            'danger'
        )
        return redirect(url_for('admin.osint_contact_types'))

    db.session.delete(config)
    db.session.commit()
    flash(f'Tipo de contacto "{config.display_name}" eliminado exitosamente', 'success')
    return redirect(url_for('admin.osint_contact_types'))


@admin_bp.route('/api-keys/<int:key_id>/test', methods=['POST'])
@login_required
@require_role('admin')
@audit_action('ADMIN_API_KEY_TEST', 'admin')
def test_api_key(key_id):
    """Test an API key."""
    from app.models.api_key import ApiKey

    api_key = ApiKey.query.get_or_404(key_id)

    if api_key.is_deleted or not api_key.is_active:
        return jsonify({
            'success': False,
            'error': 'La API Key no está activa'
        }), 400

    # Test the API key based on service
    if api_key.service_name == 'ipqualityscore':
        from app.services.ipqualityscore_service import IPQualityScoreService

        service = IPQualityScoreService(api_key)
        test_result = service.test_connection()

        if test_result['success']:
            api_key.increment_usage()
            return jsonify({
                'success': True,
                'message': 'Conexión exitosa con IPQualityScore',
                'details': test_result.get('details', {})
            })
        else:
            return jsonify({
                'success': False,
                'error': test_result.get('error', 'Error desconocido')
            }), 400
    elif api_key.service_name == 'peopledatalabs':
        from app.services.pdl_service import PDLService

        service = PDLService(api_key)
        test_result = service.test_connection()

        if test_result['success']:
            return jsonify({
                'success': True,
                'message': test_result.get('message', 'Conexión exitosa con PeopleDataLabs'),
            })
        else:
            return jsonify({
                'success': False,
                'error': test_result.get('error', 'Error desconocido'),
            }), 400
    else:
        return jsonify({
            'success': False,
            'error': 'Servicio no soportado para testing'
        }), 400
