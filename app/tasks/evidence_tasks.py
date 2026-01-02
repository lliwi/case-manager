"""
Evidence processing tasks.

Tasks for hash calculation, encryption, and metadata extraction.
"""
import os
import hashlib
from app.tasks.celery_app import celery
from app.utils.crypto import encrypt_file
from app.utils.hashing import calculate_file_hashes


@celery.task(name='app.tasks.evidence.process_evidence')
def process_evidence(evidence_id, file_path):
    """
    Process uploaded evidence: calculate hashes and encrypt.

    Args:
        evidence_id: Evidence database ID
        file_path: Path to uploaded file

    Returns:
        dict: Processing results with hashes and encrypted path
    """
    try:
        # Calculate hashes
        hashes = calculate_file_hashes(file_path)
        sha256_hash = hashes['sha256']
        sha512_hash = hashes['sha512']

        # Encrypt file
        encryption_key = os.getenv('EVIDENCE_ENCRYPTION_KEY')
        encrypted_path = encrypt_file(file_path, encryption_key)

        # Remove original unencrypted file
        if os.path.exists(file_path):
            os.remove(file_path)

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


@celery.task(name='app.tasks.evidence.extract_metadata')
def extract_metadata(evidence_id, file_path, evidence_type):
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


@celery.task(name='app.tasks.evidence.verify_integrity')
def verify_integrity(evidence_id, file_path, expected_sha256, expected_sha512):
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
        hashes = calculate_file_hashes(file_path)
        current_sha256 = hashes['sha256']
        current_sha512 = hashes['sha512']

        sha256_match = current_sha256 == expected_sha256
        sha512_match = current_sha512 == expected_sha512

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
