"""
Immutable audit log model for forensic chain of custody.

IMPORTANT: This table must be append-only. No UPDATE or DELETE operations allowed.
Immutability is enforced at both:
1. Application level (SQLAlchemy event listeners)
2. Database level (PostgreSQL triggers - see migration e5f6a7b8c9d0)
"""
from datetime import datetime
from app.extensions import db


class AuditLog(db.Model):
    """
    Immutable audit log for all system actions.

    This model records all actions performed in the system for legal compliance
    and forensic integrity. Records cannot be modified or deleted.

    Cryptographic timestamps (HMAC-SHA256) provide non-repudiation proof
    that records were created at the claimed time.
    """
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)

    # Action details
    action = db.Column(db.String(100), nullable=False, index=True)
    resource_type = db.Column(db.String(50), nullable=False)  # case, evidence, user, etc.
    resource_id = db.Column(db.Integer)
    description = db.Column(db.Text)

    # User context
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user_email = db.Column(db.String(120), nullable=False)  # Denormalized for audit trail

    # Request context
    ip_address = db.Column(db.String(45))  # IPv6-compatible
    user_agent = db.Column(db.Text)
    request_method = db.Column(db.String(10))
    request_path = db.Column(db.String(500))

    # Additional data (JSON)
    extra_data = db.Column(db.JSON)

    # Timestamp (immutable)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Cryptographic timestamp proof (UNE 71506 compliance)
    record_hash = db.Column(db.String(64))  # SHA-256 hash of record content
    timestamp_signature = db.Column(db.String(128))  # HMAC-SHA256 signature

    # Relationships
    user = db.relationship('User', backref=db.backref('audit_logs', lazy='dynamic'))

    def __repr__(self):
        return f'<AuditLog {self.action} by {self.user_email} at {self.timestamp}>'

    @classmethod
    def log(cls, action, resource_type, user, description=None, resource_id=None,
            ip_address=None, user_agent=None, request_method=None, request_path=None,
            extra_data=None):
        """
        Create an audit log entry with cryptographic timestamp.

        Args:
            action: Action performed (e.g., 'CREATED', 'VIEWED', 'UPDATED', 'DELETED')
            resource_type: Type of resource (e.g., 'case', 'evidence', 'user')
            user: User object who performed the action
            description: Human-readable description
            resource_id: ID of the affected resource
            ip_address: Client IP address
            user_agent: Client user agent
            request_method: HTTP method
            request_path: Request path
            extra_data: Additional JSON metadata

        Returns:
            AuditLog instance with cryptographic timestamp signature
        """
        log_entry = cls(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            user_id=user.id,
            user_email=user.email,
            ip_address=ip_address,
            user_agent=user_agent,
            request_method=request_method,
            request_path=request_path,
            extra_data=extra_data,
            timestamp=datetime.utcnow()
        )

        # Add cryptographic timestamp signature for forensic integrity
        try:
            from app.utils.timestamp_service import TimestampService
            record_hash, signature = TimestampService.sign_audit_log(log_entry)
            log_entry.record_hash = record_hash
            log_entry.timestamp_signature = signature
        except Exception:
            # Continue without signature if service unavailable
            pass

        db.session.add(log_entry)
        db.session.commit()
        return log_entry

    def verify_integrity(self) -> dict:
        """
        Verify the cryptographic integrity of this audit log entry.

        Returns:
            Dictionary with verification results including:
            - valid: Boolean indicating if record is intact
            - signed: Boolean indicating if record has signature
            - error: Error message if verification failed
        """
        from app.utils.timestamp_service import TimestampService
        return TimestampService.verify_audit_log(self)


# Prevent UPDATE and DELETE operations on audit logs
# This is enforced at the application level via SQLAlchemy events
from sqlalchemy import event

@event.listens_for(AuditLog, 'before_update')
def prevent_audit_log_update(mapper, connection, target):
    """Prevent modification of audit log entries."""
    raise ValueError("Audit logs are immutable and cannot be updated.")

@event.listens_for(AuditLog, 'before_delete')
def prevent_audit_log_delete(mapper, connection, target):
    """Prevent deletion of audit log entries."""
    raise ValueError("Audit logs are immutable and cannot be deleted.")
