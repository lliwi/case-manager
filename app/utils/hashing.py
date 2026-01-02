"""
Hashing utilities for evidence integrity verification.

Implements SHA-256 and SHA-512 hashing per UNE 71506 forensic standards.
"""
import hashlib
from typing import Dict


def calculate_file_hashes(file_path):
    """
    Calculate SHA-256 and SHA-512 hashes of a file.

    Args:
        file_path: Path to the file

    Returns:
        dict: Dictionary with 'sha256' and 'sha512' hash values (hex)

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    sha256_hash = hashlib.sha256()
    sha512_hash = hashlib.sha512()

    # Read file in chunks to handle large files
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):  # 8KB chunks
            sha256_hash.update(chunk)
            sha512_hash.update(chunk)

    return {
        'sha256': sha256_hash.hexdigest(),
        'sha512': sha512_hash.hexdigest()
    }


def calculate_data_hashes(data):
    """
    Calculate SHA-256 and SHA-512 hashes of data in memory.

    Args:
        data: Bytes to hash

    Returns:
        dict: Dictionary with 'sha256' and 'sha512' hash values (hex)
    """
    sha256_hash = hashlib.sha256(data)
    sha512_hash = hashlib.sha512(data)

    return {
        'sha256': sha256_hash.hexdigest(),
        'sha512': sha512_hash.hexdigest()
    }


def verify_file_hash(file_path, expected_sha256=None, expected_sha512=None):
    """
    Verify file integrity by comparing hashes.

    Args:
        file_path: Path to the file
        expected_sha256: Expected SHA-256 hash (hex)
        expected_sha512: Expected SHA-512 hash (hex)

    Returns:
        dict: Verification results with 'sha256_match' and 'sha512_match' booleans

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If no expected hash is provided
    """
    if not expected_sha256 and not expected_sha512:
        raise ValueError("At least one expected hash must be provided")

    calculated = calculate_file_hashes(file_path)

    result = {}

    if expected_sha256:
        result['sha256_match'] = (calculated['sha256'].lower() == expected_sha256.lower())
        result['sha256_calculated'] = calculated['sha256']

    if expected_sha512:
        result['sha512_match'] = (calculated['sha512'].lower() == expected_sha512.lower())
        result['sha512_calculated'] = calculated['sha512']

    result['verified'] = all([
        result.get('sha256_match', True),
        result.get('sha512_match', True)
    ])

    return result


def hash_string(text, algorithm='sha256'):
    """
    Hash a string using the specified algorithm.

    Args:
        text: String to hash
        algorithm: Hash algorithm ('sha256' or 'sha512')

    Returns:
        str: Hex-encoded hash

    Raises:
        ValueError: If algorithm is not supported
    """
    if algorithm == 'sha256':
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    elif algorithm == 'sha512':
        return hashlib.sha512(text.encode('utf-8')).hexdigest()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")
