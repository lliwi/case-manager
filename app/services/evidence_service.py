"""
Evidence service for handling file uploads with forensic integrity.

Implements UNE 71506 preservation and acquisition phases.
"""
from app.models.evidence import Evidence, EvidenceType, ChainOfCustody
from app.extensions import db
from app.utils.hashing import calculate_file_hashes
from app.utils.crypto import encrypt_file
from flask import current_app
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import mimetypes


class EvidenceService:
    """Service for evidence management."""

    # Allowed file extensions per evidence type
    ALLOWED_EXTENSIONS = {
        EvidenceType.IMAGEN: {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'tif', 'webp', 'heic'},
        EvidenceType.VIDEO: {'mp4', 'avi', 'mov', 'mkv', 'flv', 'wmv', 'webm', 'm4v'},
        EvidenceType.AUDIO: {'mp3', 'wav', 'aac', 'flac', 'm4a', 'ogg', 'wma'},
        EvidenceType.DOCUMENTO: {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'odt', 'txt'},
        EvidenceType.EMAIL: {'eml', 'msg', 'mbox'},
        EvidenceType.CAPTURA_WEB: {'html', 'htm', 'mht', 'mhtml'},
        EvidenceType.DATOS_DIGITALES: {'json', 'xml', 'csv', 'sql', 'db', 'sqlite'},
        EvidenceType.OTROS: set(),  # Any extension allowed
    }

    @staticmethod
    def get_evidence_type_from_extension(filename):
        """
        Determine evidence type from file extension.

        Args:
            filename: Original filename

        Returns:
            EvidenceType enum value
        """
        ext = os.path.splitext(filename)[1].lower().lstrip('.')

        for evidence_type, extensions in EvidenceService.ALLOWED_EXTENSIONS.items():
            if ext in extensions:
                return evidence_type

        # Check for archives
        if ext in {'zip', 'rar', '7z', 'tar', 'gz', 'bz2'}:
            return EvidenceType.DATOS_DIGITALES

        return EvidenceType.OTROS

    @staticmethod
    def validate_file(file, case):
        """
        Validate uploaded file.

        Args:
            file: FileStorage object
            case: Case instance

        Returns:
            dict with validation results

        Raises:
            ValueError: If validation fails
        """
        if not file:
            raise ValueError("No file provided")

        if file.filename == '':
            raise ValueError("Empty filename")

        # Check file size
        max_size = current_app.config.get('MAX_CONTENT_LENGTH', 500 * 1024 * 1024)
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset to beginning

        if file_size > max_size:
            raise ValueError(f"File too large: {file_size} bytes (max: {max_size})")

        if file_size == 0:
            raise ValueError("File is empty")

        # Check case is valid
        if not case.legitimacy_validated:
            raise ValueError("Cannot upload evidence to case without validated legitimacy")

        if case.crime_detected and not case.crime_reported:
            raise ValueError("Cannot upload evidence to case with unreported crimes")

        return {
            'valid': True,
            'file_size': file_size,
            'filename': file.filename
        }

    @staticmethod
    def upload_evidence(file, case, user, description=None, tags=None,
                       acquisition_date=None, acquisition_method=None,
                       source_device=None, source_location=None, acquisition_notes=None):
        """
        Upload evidence with forensic integrity.

        Process:
        1. Validate file
        2. Calculate hashes (SHA-256, SHA-512)
        3. Encrypt file (AES-256-GCM)
        4. Save encrypted file
        5. Create Evidence record
        6. Log to chain of custody

        Args:
            file: FileStorage object
            case: Case instance
            user: User uploading
            description: Evidence description
            tags: Comma-separated tags
            acquisition_date: When evidence was acquired
            acquisition_method: How it was acquired
            source_device: Source device
            source_location: Source location
            acquisition_notes: Acquisition notes

        Returns:
            Evidence instance

        Raises:
            ValueError: If validation or processing fails
        """
        # Validate
        validation = EvidenceService.validate_file(file, case)

        # Secure filename
        original_filename = file.filename
        safe_filename = secure_filename(original_filename)

        # Determine evidence type
        evidence_type = EvidenceService.get_evidence_type_from_extension(original_filename)

        # Get MIME type
        mime_type = mimetypes.guess_type(original_filename)[0]

        # Create unique filename
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{case.numero_orden}_{timestamp}_{safe_filename}"

        # Save to temporary location first
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        temp_path = os.path.join(upload_folder, unique_filename)

        file.save(temp_path)

        try:
            # Calculate hashes BEFORE encryption
            hashes = calculate_file_hashes(temp_path)

            # Encrypt file
            evidence_folder = current_app.config['EVIDENCE_FOLDER']
            os.makedirs(evidence_folder, exist_ok=True)
            encrypted_filename = f"{unique_filename}.enc"
            encrypted_path = os.path.join(evidence_folder, encrypted_filename)

            encryption_key = current_app.config['EVIDENCE_ENCRYPTION_KEY']
            if not encryption_key:
                raise ValueError("EVIDENCE_ENCRYPTION_KEY not configured")

            encryption_metadata = encrypt_file(temp_path, encrypted_path, encryption_key)

            # Create Evidence record
            evidence = Evidence(
                case_id=case.id,
                filename=unique_filename,
                original_filename=original_filename,
                file_path=encrypted_path,
                file_size=validation['file_size'],
                mime_type=mime_type,
                evidence_type=evidence_type,
                sha256_hash=hashes['sha256'],
                sha512_hash=hashes['sha512'],
                timestamp=datetime.utcnow(),
                is_encrypted=True,
                encryption_algorithm=encryption_metadata['algorithm'],
                encryption_nonce=encryption_metadata['nonce'],
                acquisition_date=acquisition_date or datetime.utcnow(),
                acquisition_method=acquisition_method or 'Direct upload',
                source_device=source_device,
                source_location=source_location,
                acquisition_notes=acquisition_notes,
                description=description,
                tags=tags,
                uploaded_by_id=user.id,
                uploaded_at=datetime.utcnow(),
                integrity_verified=True,
                last_verification_date=datetime.utcnow()
            )

            db.session.add(evidence)
            db.session.flush()  # Get evidence ID

            # Log to chain of custody
            ChainOfCustody.log(
                action='UPLOADED',
                evidence=evidence,
                user=user,
                notes=f'Evidence uploaded: {original_filename}',
                metadata={
                    'file_size': validation['file_size'],
                    'mime_type': mime_type,
                    'evidence_type': evidence_type.value,
                    'encryption': encryption_metadata
                },
                hash_verified=True,
                hash_match=True,
                sha256=hashes['sha256'],
                sha512=hashes['sha512']
            )

            db.session.commit()

            # Log to audit
            from app.models.audit import AuditLog
            AuditLog.log(
                action='EVIDENCE_UPLOADED',
                resource_type='evidence',
                resource_id=evidence.id,
                user=user,
                description=f'Uploaded evidence {original_filename} to case {case.numero_orden}',
                extra_data={
                    'case_id': case.id,
                    'file_size': validation['file_size'],
                    'sha256': hashes['sha256']
                }
            )

            return evidence

        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)

    @staticmethod
    def verify_evidence_integrity(evidence, user):
        """
        Verify evidence integrity and log to chain of custody.

        Args:
            evidence: Evidence instance
            user: User performing verification

        Returns:
            dict with verification results
        """
        result = evidence.verify_integrity()

        # Log to chain of custody
        ChainOfCustody.log(
            action='HASH_VERIFIED',
            evidence=evidence,
            user=user,
            notes='Integrity verification performed',
            hash_verified=True,
            hash_match=result['verified'],
            sha256=result.get('sha256_calculated'),
            sha512=result.get('sha512_calculated')
        )

        # If verification failed, log to audit
        if not result['verified']:
            from app.models.audit import AuditLog
            AuditLog.log(
                action='EVIDENCE_INTEGRITY_FAILED',
                resource_type='evidence',
                resource_id=evidence.id,
                user=user,
                description=f'Integrity verification FAILED for evidence {evidence.filename}',
                metadata=result
            )

        return result

    @staticmethod
    def get_evidence_stats(case_id=None, user_id=None):
        """
        Get evidence statistics.

        Args:
            case_id: Filter by case
            user_id: Filter by user

        Returns:
            dict with statistics
        """
        query = Evidence.query.filter_by(is_deleted=False)

        if case_id:
            query = query.filter_by(case_id=case_id)

        if user_id:
            query = query.filter_by(uploaded_by_id=user_id)

        total_count = query.count()
        total_size = db.session.query(db.func.sum(Evidence.file_size)).filter(
            Evidence.is_deleted == False
        )

        if case_id:
            total_size = total_size.filter(Evidence.case_id == case_id)
        if user_id:
            total_size = total_size.filter(Evidence.uploaded_by_id == user_id)

        total_size = total_size.scalar() or 0

        # Count by type
        by_type = {}
        for evidence_type in EvidenceType:
            count = query.filter_by(evidence_type=evidence_type).count()
            by_type[evidence_type.value] = count

        # Integrity status
        verified_count = query.filter_by(integrity_verified=True).count()

        return {
            'total_count': total_count,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'by_type': by_type,
            'verified_count': verified_count,
            'verification_rate': round((verified_count / total_count * 100), 1) if total_count > 0 else 0
        }

    @staticmethod
    def extract_metadata(evidence, user):
        """
        Extract metadata from evidence using appropriate plugin.

        Args:
            evidence: Evidence instance
            user: User requesting extraction

        Returns:
            dict with extracted metadata
        """
        # This will be implemented when plugin system is ready (Phase 8)
        # For now, just log the attempt
        ChainOfCustody.log(
            action='METADATA_EXTRACTION_REQUESTED',
            evidence=evidence,
            user=user,
            notes='Metadata extraction requested (plugin system pending)'
        )

        return {'status': 'pending', 'message': 'Plugin system not yet implemented'}
