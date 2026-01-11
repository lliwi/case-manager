"""
API Key model for managing third-party service credentials.

Stores API keys for external services like IPQualityScore with encryption and audit trail.
Follows security best practices with field-level encryption for sensitive data.
"""
from datetime import datetime
from app.extensions import db
from cryptography.fernet import Fernet
import os

class ApiKey(db.Model):
    """
    API Key model for storing encrypted third-party service credentials.

    Attributes:
        id: Primary key
        service_name: Name of the service (e.g., 'ipqualityscore', 'osint_api')
        key_name: User-friendly name for the key (e.g., 'Production Key', 'Testing Key')
        api_key_encrypted: Encrypted API key value
        is_active: Whether the key is currently active
        description: Optional description of the key's purpose
        created_at: Timestamp of key creation
        updated_at: Timestamp of last update
        created_by_id: User who created the key
        last_used_at: Timestamp of last usage
        usage_count: Number of times the key has been used
    """
    __tablename__ = 'api_keys'

    id = db.Column(db.Integer, primary_key=True)
    service_name = db.Column(db.String(100), nullable=False, index=True)
    key_name = db.Column(db.String(200), nullable=False)
    api_key_encrypted = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    description = db.Column(db.Text)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = db.Column(db.DateTime)

    # Usage tracking
    usage_count = db.Column(db.Integer, default=0, nullable=False)

    # Relationships
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_by = db.relationship('User', backref='created_api_keys', foreign_keys=[created_by_id])

    # Soft delete support
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime)
    deleted_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    deleted_by = db.relationship('User', foreign_keys=[deleted_by_id])

    def __init__(self, service_name, key_name, api_key, created_by_id, description=None):
        """
        Initialize a new API key with encryption.

        Args:
            service_name: Name of the service
            key_name: User-friendly name for the key
            api_key: Plain text API key to encrypt
            created_by_id: ID of the user creating the key
            description: Optional description
        """
        self.service_name = service_name
        self.key_name = key_name
        self.description = description
        self.created_by_id = created_by_id
        self.set_api_key(api_key)

    def get_encryption_key(self):
        """
        Get or generate encryption key for API keys.

        Returns:
            bytes: Fernet encryption key
        """
        # Use evidence encryption key or generate a specific one for API keys
        key = os.environ.get('API_KEY_ENCRYPTION_KEY') or os.environ.get('EVIDENCE_ENCRYPTION_KEY')

        if not key:
            # In development, generate a key (in production this should be set)
            from flask import current_app
            if current_app.config.get('ENV') == 'development':
                key = Fernet.generate_key().decode()
            else:
                raise ValueError("API_KEY_ENCRYPTION_KEY or EVIDENCE_ENCRYPTION_KEY must be set in production")

        # Ensure key is properly formatted (32 bytes base64 encoded for Fernet)
        if isinstance(key, str):
            if len(key) == 64:  # Hex string
                # Convert hex to bytes, then base64 encode for Fernet
                import base64
                key_bytes = bytes.fromhex(key)[:32]  # Take first 32 bytes
                key = base64.urlsafe_b64encode(key_bytes)
            else:
                key = key.encode()

        return key

    def set_api_key(self, plain_key):
        """
        Encrypt and store the API key.

        Args:
            plain_key: Plain text API key to encrypt
        """
        encryption_key = self.get_encryption_key()
        fernet = Fernet(encryption_key)
        self.api_key_encrypted = fernet.encrypt(plain_key.encode()).decode()

    def get_api_key(self):
        """
        Decrypt and return the API key.

        Returns:
            str: Decrypted API key
        """
        encryption_key = self.get_encryption_key()
        fernet = Fernet(encryption_key)
        return fernet.decrypt(self.api_key_encrypted.encode()).decode()

    def get_masked_key(self):
        """
        Return a masked version of the API key for display.

        Returns:
            str: Masked API key (e.g., 'bhje****DKuqG')
        """
        try:
            plain_key = self.get_api_key()
            if len(plain_key) <= 8:
                return '****' + plain_key[-4:]
            return plain_key[:4] + '****' + plain_key[-4:]
        except Exception:
            return '****ERROR****'

    def increment_usage(self):
        """
        Increment usage counter and update last used timestamp.
        """
        self.usage_count += 1
        self.last_used_at = datetime.utcnow()
        db.session.commit()

    def soft_delete(self, user):
        """
        Soft delete the API key.

        Args:
            user: User performing the deletion
        """
        self.is_deleted = True
        self.is_active = False
        self.deleted_at = datetime.utcnow()
        self.deleted_by_id = user.id
        db.session.commit()

    @staticmethod
    def get_active_key(service_name):
        """
        Get an active API key for a specific service.

        Args:
            service_name: Name of the service

        Returns:
            ApiKey: Active API key or None
        """
        return ApiKey.query.filter_by(
            service_name=service_name,
            is_active=True,
            is_deleted=False
        ).order_by(ApiKey.last_used_at.asc().nullsfirst()).first()

    def to_dict(self):
        """
        Convert API key to dictionary for JSON serialization.

        Returns:
            dict: API key data
        """
        return {
            'id': self.id,
            'service_name': self.service_name,
            'key_name': self.key_name,
            'masked_key': self.get_masked_key(),
            'is_active': self.is_active,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'usage_count': self.usage_count,
            'created_by': self.created_by.email if self.created_by else None
        }

    def __repr__(self):
        return f'<ApiKey {self.service_name}:{self.key_name}>'
