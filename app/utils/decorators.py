"""
Custom decorators for authentication, authorization, and auditing.
"""
from functools import wraps
from flask import request, flash, redirect, url_for, abort
from flask_login import current_user


def audit_action(action, resource_type):
    """
    Decorator to automatically log actions to the audit trail.

    Args:
        action: Action being performed (e.g., 'CREATED', 'VIEWED', 'UPDATED')
        resource_type: Type of resource (e.g., 'case', 'evidence', 'user')

    Usage:
        @audit_action('VIEWED', 'case')
        def view_case(case_id):
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Execute the wrapped function first
            result = f(*args, **kwargs)

            # Log the action
            if current_user.is_authenticated:
                from app.models.audit import AuditLog

                # Extract resource_id from kwargs or args
                resource_id = kwargs.get('id') or kwargs.get('case_id') or \
                             kwargs.get('evidence_id') or kwargs.get('user_id')

                # Get request context
                ip_address = request.remote_addr
                user_agent = request.headers.get('User-Agent')
                request_method = request.method
                request_path = request.path

                AuditLog.log(
                    action=action,
                    resource_type=resource_type,
                    user=current_user._get_current_object(),
                    resource_id=resource_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    request_method=request_method,
                    request_path=request_path
                )

            return result
        return decorated_function
    return decorator


def require_role(role_name):
    """
    Decorator to require a specific role for accessing a route.

    Args:
        role_name: Required role name (e.g., 'admin', 'detective')

    Usage:
        @require_role('admin')
        def admin_panel():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Por favor, inicie sesión para acceder a esta página.', 'warning')
                return redirect(url_for('auth.login'))

            if not current_user.has_role(role_name):
                flash('No tiene permisos para acceder a esta página.', 'danger')
                abort(403)

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_detective():
    """
    Decorator to require detective role.

    Usage:
        @require_detective()
        def detective_only_route():
            ...
    """
    return require_role('detective')


def require_admin():
    """
    Decorator to require admin role.

    Usage:
        @require_admin()
        def admin_only_route():
            ...
    """
    return require_role('admin')


def mfa_required(f):
    """
    Decorator to require MFA verification.

    Usage:
        @mfa_required
        def sensitive_action():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))

        # If user has MFA enabled, check if they've verified in this session
        if current_user.mfa_enabled:
            from flask import session
            if not session.get('mfa_verified'):
                flash('Se requiere verificación MFA para esta acción.', 'warning')
                return redirect(url_for('auth.verify_mfa', next=request.url))

        return f(*args, **kwargs)
    return decorated_function
