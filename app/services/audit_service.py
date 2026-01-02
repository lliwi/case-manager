"""
Audit logging service for forensic chain of custody.
"""
from flask import request
from app.models.audit import AuditLog
from app.extensions import db


def log_action(action, resource_type, user, description=None, resource_id=None, metadata=None):
    """
    Log an action to the audit trail.

    Args:
        action: Action performed (e.g., 'CREATED', 'VIEWED', 'UPDATED')
        resource_type: Type of resource (e.g., 'case', 'evidence')
        user: User object who performed the action
        description: Human-readable description
        resource_id: ID of the affected resource
        metadata: Additional JSON metadata

    Returns:
        AuditLog instance
    """
    return AuditLog.log(
        action=action,
        resource_type=resource_type,
        user=user,
        description=description,
        resource_id=resource_id,
        ip_address=request.remote_addr if request else None,
        user_agent=request.headers.get('User-Agent') if request else None,
        request_method=request.method if request else None,
        request_path=request.path if request else None,
        metadata=metadata
    )
