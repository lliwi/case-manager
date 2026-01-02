"""
Evidence and Chain of Custody models.

Implements UNE 71506 forensic standards for digital evidence management.
"""
from datetime import datetime
from app.extensions import db
import enum


class EvidenceType(enum.Enum):
    """Evidence types."""
    IMAGEN = "Imagen"
    VIDEO = "Vídeo"
    AUDIO = "Audio"
    DOCUMENTO = "Documento"
    CAPTURA_WEB = "Captura Web"
    DATOS_DIGITALES = "Datos Digitales"
    EMAIL = "Email"
    OTROS = "Otros"


class Evidence(db.Model):
    """
    Evidence model with forensic chain of custody.

    Implements UNE 71506 requirements:
    - Preservation: Encrypted storage, hash calculation
    - Acquisition: Metadata capture, timestamp
    - Documentation: Chain of custody
    - Analysis: Plugin-based extraction
    - Presentation: Export with integrity proof
    """
    __tablename__ = 'evidences'

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), nullable=False)

    # File information
    filename = db.Column(db.String(500), nullable=False)
    original_filename = db.Column(db.String(500), nullable=False)
    file_path = db.Column(db.String(1000), nullable=False)  # Encrypted file path
    file_size = db.Column(db.BigInteger, nullable=False)  # Bytes
    mime_type = db.Column(db.String(100))
    evidence_type = db.Column(db.Enum(EvidenceType), nullable=False)

    # Forensic integrity (UNE 71506)
    sha256_hash = db.Column(db.String(64), nullable=False, index=True)
    sha512_hash = db.Column(db.String(128), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    trusted_timestamp = db.Column(db.Text)  # RFC 3161 timestamp proof (optional)

    # Encryption
    is_encrypted = db.Column(db.Boolean, default=True, nullable=False)
    encryption_algorithm = db.Column(db.String(50), default='AES-256-GCM')
    encryption_nonce = db.Column(db.String(24))  # Hex-encoded nonce

    # Acquisition metadata (UNE 71506 - Acquisition phase)
    acquisition_date = db.Column(db.DateTime)
    acquisition_method = db.Column(db.String(200))  # e.g., "Direct upload", "Forensic copy", "Network capture"
    acquisition_tool = db.Column(db.String(200))  # Tool used for acquisition
    acquisition_notes = db.Column(db.Text)

    # Source information
    source_device = db.Column(db.String(200))  # Device where evidence was obtained
    source_location = db.Column(db.String(500))  # Location of acquisition

    # Geolocation (if available from EXIF or manual)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    location_description = db.Column(db.String(500))

    # Extracted metadata (JSON)
    extracted_metadata = db.Column(db.JSON)  # EXIF, PDF metadata, etc.

    # Description and tags
    description = db.Column(db.Text)
    tags = db.Column(db.Text)  # Comma-separated tags

    # Graph linkage
    neo4j_node_id = db.Column(db.String(100))  # Reference to Neo4j Evidence node

    # Upload info
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Verification status
    integrity_verified = db.Column(db.Boolean, default=False)
    last_verification_date = db.Column(db.DateTime)

    # Soft delete
    is_deleted = db.Column(db.Boolean, default=False)
    deleted_at = db.Column(db.DateTime)
    deleted_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Relationships
    case = db.relationship('Case', backref=db.backref('evidences', lazy='dynamic'))
    uploaded_by = db.relationship('User', foreign_keys=[uploaded_by_id], backref='uploaded_evidences')
    deleted_by = db.relationship('User', foreign_keys=[deleted_by_id])
    chain_of_custody = db.relationship('ChainOfCustody', backref='evidence', lazy='dynamic',
                                      cascade='all, delete-orphan', order_by='ChainOfCustody.timestamp.desc()')

    def __repr__(self):
        return f'<Evidence {self.filename}>'

    def verify_integrity(self):
        """
        Verify file integrity by recalculating hashes.

        Returns:
            dict with verification results
        """
        from app.utils.hashing import verify_file_hash
        from app.utils.crypto import decrypt_file
        import os
        import tempfile

        # If encrypted, decrypt to temp file first
        if self.is_encrypted:
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name

            try:
                from flask import current_app
                encryption_key = current_app.config['EVIDENCE_ENCRYPTION_KEY']
                decrypt_file(self.file_path, temp_path, encryption_key)

                result = verify_file_hash(
                    temp_path,
                    expected_sha256=self.sha256_hash,
                    expected_sha512=self.sha512_hash
                )
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        else:
            result = verify_file_hash(
                self.file_path,
                expected_sha256=self.sha256_hash,
                expected_sha512=self.sha512_hash
            )

        self.integrity_verified = result['verified']
        self.last_verification_date = datetime.utcnow()
        db.session.commit()

        return result

    def get_decrypted_path(self):
        """
        Get temporary decrypted file path.

        Returns:
            str: Path to temporary decrypted file
        """
        import tempfile
        from app.utils.crypto import decrypt_file
        from flask import current_app

        if not self.is_encrypted:
            return self.file_path

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(self.original_filename)[1])
        temp_path = temp_file.name
        temp_file.close()

        encryption_key = current_app.config['EVIDENCE_ENCRYPTION_KEY']
        decrypt_file(self.file_path, temp_path, encryption_key)

        return temp_path

    def soft_delete(self, user):
        """Soft delete evidence."""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        self.deleted_by_id = user.id
        db.session.commit()

        # Log deletion
        from app.models.audit import AuditLog
        AuditLog.log(
            action='EVIDENCE_DELETED',
            resource_type='evidence',
            resource_id=self.id,
            user=user,
            description=f'Evidence {self.filename} soft deleted from case {self.case.numero_orden}'
        )

    def get_file_extension(self):
        """Get file extension."""
        import os
        return os.path.splitext(self.original_filename)[1].lower()

    def is_image(self):
        """Check if evidence is an image."""
        return self.evidence_type == EvidenceType.IMAGEN

    def is_video(self):
        """Check if evidence is a video."""
        return self.evidence_type == EvidenceType.VIDEO

    def is_document(self):
        """Check if evidence is a document."""
        return self.evidence_type == EvidenceType.DOCUMENTO


class ChainOfCustody(db.Model):
    """
    Immutable chain of custody log.

    Records every interaction with evidence for forensic integrity.
    """
    __tablename__ = 'chain_of_custody'

    id = db.Column(db.Integer, primary_key=True)
    evidence_id = db.Column(db.Integer, db.ForeignKey('evidences.id'), nullable=False)

    # Event details
    action = db.Column(db.String(100), nullable=False, index=True)
    # Actions: UPLOADED, VIEWED, DOWNLOADED, EXPORTED, HASH_VERIFIED, METADATA_EXTRACTED, ANALYZED

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Request context
    ip_address = db.Column(db.String(45))  # IPv6-compatible
    user_agent = db.Column(db.Text)
    request_method = db.Column(db.String(10))
    request_path = db.Column(db.String(500))

    # Action-specific data
    notes = db.Column(db.Text)
    extra_data = db.Column(db.JSON)

    # Integrity verification (for HASH_VERIFIED action)
    hash_verified = db.Column(db.Boolean)
    hash_match = db.Column(db.Boolean)
    sha256_calculated = db.Column(db.String(64))
    sha512_calculated = db.Column(db.String(128))

    # Relationships
    user = db.relationship('User', backref=db.backref('custody_actions', lazy='dynamic'))

    def __repr__(self):
        return f'<ChainOfCustody {self.action} on Evidence#{self.evidence_id}>'

    @staticmethod
    def log(action, evidence, user, notes=None, extra_data=None,
            hash_verified=None, hash_match=None, sha256=None, sha512=None):
        """
        Log chain of custody entry.

        Args:
            action: Action performed (UPLOADED, VIEWED, etc.)
            evidence: Evidence instance
            user: User who performed action
            notes: Optional notes
            extra_data: Additional JSON metadata
            hash_verified: Whether hash was verified
            hash_match: Whether hash matched
            sha256: Calculated SHA-256 hash
            sha512: Calculated SHA-512 hash

        Returns:
            ChainOfCustody instance
        """
        from flask import request

        entry = ChainOfCustody(
            evidence_id=evidence.id,
            action=action,
            user_id=user.id,
            notes=notes,
            extra_data=extra_data,
            hash_verified=hash_verified,
            hash_match=hash_match,
            sha256_calculated=sha256,
            sha512_calculated=sha512
        )

        # Capture request context if available
        if request:
            entry.ip_address = request.remote_addr
            entry.user_agent = request.headers.get('User-Agent')
            entry.request_method = request.method
            entry.request_path = request.path

        db.session.add(entry)
        db.session.commit()

        return entry


# Prevent UPDATE and DELETE operations on chain of custody
from sqlalchemy import event

@event.listens_for(ChainOfCustody, 'before_update')
def prevent_custody_update(mapper, connection, target):
    """Prevent modification of chain of custody entries."""
    raise ValueError("Chain of custody entries are immutable and cannot be updated.")

@event.listens_for(ChainOfCustody, 'before_delete')
def prevent_custody_delete(mapper, connection, target):
    """Prevent deletion of chain of custody entries."""
    raise ValueError("Chain of custody entries are immutable and cannot be deleted.")
