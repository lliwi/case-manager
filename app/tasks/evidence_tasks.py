"""
Evidence processing tasks.

Tasks for hash calculation, encryption, and metadata extraction.
"""
import os
import hashlib
from app.tasks.celery_app import celery
from app.utils.crypto import encrypt_file
from app.utils.hashing import calculate_file_hashes


@celery.task(
    name='app.tasks.evidence.process_evidence',
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3
)
def process_evidence(self, evidence_id, file_path):
    """
    Process uploaded evidence: calculate hashes and encrypt.

    Args:
        evidence_id: Evidence database ID
        file_path: Path to uploaded file

    Returns:
        dict: Processing results with hashes and encrypted path
    """
    try:
        # Update progress: Starting
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 100, 'status': 'Iniciando procesamiento...', 'progress': 0}
        )

        # Calculate hashes
        self.update_state(
            state='PROGRESS',
            meta={'current': 25, 'total': 100, 'status': 'Calculando hashes SHA-256 y SHA-512...', 'progress': 25}
        )
        hashes = calculate_file_hashes(file_path)
        sha256_hash = hashes['sha256']
        sha512_hash = hashes['sha512']

        # Encrypt file
        self.update_state(
            state='PROGRESS',
            meta={'current': 60, 'total': 100, 'status': 'Encriptando archivo con AES-256-GCM...', 'progress': 60}
        )
        encryption_key = os.getenv('EVIDENCE_ENCRYPTION_KEY')
        encrypted_path = encrypt_file(file_path, encryption_key)

        # Remove original unencrypted file
        self.update_state(
            state='PROGRESS',
            meta={'current': 90, 'total': 100, 'status': 'Eliminando archivo original...', 'progress': 90}
        )
        if os.path.exists(file_path):
            os.remove(file_path)

        # Complete
        self.update_state(
            state='PROGRESS',
            meta={'current': 100, 'total': 100, 'status': 'Completado', 'progress': 100}
        )

        return {
            'success': True,
            'evidence_id': evidence_id,
            'sha256': sha256_hash,
            'sha512': sha512_hash,
            'encrypted_path': encrypted_path,
        }

    except Exception as e:
        return {
            'success': False,
            'evidence_id': evidence_id,
            'error': str(e)
        }


@celery.task(
    name='app.tasks.evidence.extract_metadata',
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3
)
def extract_metadata(self, evidence_id, file_path, evidence_type):
    """
    Extract metadata from evidence file.

    Args:
        evidence_id: Evidence database ID
        file_path: Path to evidence file
        evidence_type: Type of evidence (IMAGE, VIDEO, DOCUMENT, etc.)

    Returns:
        dict: Extracted metadata
    """
    metadata = {
        'evidence_id': evidence_id,
        'metadata': {}
    }

    try:
        if evidence_type == 'IMAGE':
            # TODO: Extract EXIF data with Pillow/ExifTool
            pass
        elif evidence_type == 'VIDEO':
            # TODO: Extract video metadata with mutagen/ffmpeg
            pass
        elif evidence_type == 'DOCUMENTO':
            # TODO: Extract document metadata with PyPDF2/OleFile
            pass

        metadata['success'] = True

    except Exception as e:
        metadata['success'] = False
        metadata['error'] = str(e)

    return metadata


@celery.task(
    name='app.tasks.evidence.verify_integrity',
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3
)
def verify_integrity(self, evidence_id, file_path, expected_sha256, expected_sha512):
    """
    Verify evidence integrity by comparing hashes.

    Args:
        evidence_id: Evidence database ID
        file_path: Path to evidence file
        expected_sha256: Expected SHA-256 hash
        expected_sha512: Expected SHA-512 hash

    Returns:
        dict: Verification results
    """
    try:
        # Update progress: Starting verification
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 100, 'status': 'Iniciando verificación de integridad...', 'progress': 0}
        )

        # Calculate current hashes
        self.update_state(
            state='PROGRESS',
            meta={'current': 30, 'total': 100, 'status': 'Recalculando hashes del archivo...', 'progress': 30}
        )
        hashes = calculate_file_hashes(file_path)
        current_sha256 = hashes['sha256']
        current_sha512 = hashes['sha512']

        # Compare hashes
        self.update_state(
            state='PROGRESS',
            meta={'current': 70, 'total': 100, 'status': 'Comparando con hashes esperados...', 'progress': 70}
        )
        sha256_match = current_sha256 == expected_sha256
        sha512_match = current_sha512 == expected_sha512

        # Complete
        self.update_state(
            state='PROGRESS',
            meta={'current': 100, 'total': 100, 'status': 'Verificación completada', 'progress': 100}
        )

        return {
            'success': True,
            'evidence_id': evidence_id,
            'sha256_match': sha256_match,
            'sha512_match': sha512_match,
            'current_sha256': current_sha256,
            'current_sha512': current_sha512,
            'integrity_ok': sha256_match and sha512_match
        }

    except Exception as e:
        return {
            'success': False,
            'evidence_id': evidence_id,
            'error': str(e)
        }
