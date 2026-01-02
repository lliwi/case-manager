"""
Cryptographic utilities for evidence encryption.

Uses AES-256-GCM for authenticated encryption.
"""
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
import secrets


def generate_encryption_key():
    """
    Generate a random 256-bit encryption key.

    Returns:
        str: Hex-encoded encryption key
    """
    return secrets.token_hex(32)  # 32 bytes = 256 bits


def encrypt_file(input_path, output_path, key_hex):
    """
    Encrypt a file using AES-256-GCM.

    Args:
        input_path: Path to the file to encrypt
        output_path: Path where encrypted file will be saved
        key_hex: Hex-encoded encryption key (64 characters)

    Returns:
        dict: Encryption metadata (nonce, tag)

    Raises:
        ValueError: If key is invalid
        FileNotFoundError: If input file doesn't exist
    """
    if len(key_hex) != 64:
        raise ValueError("Encryption key must be 64 hex characters (256 bits)")

    # Convert hex key to bytes
    key = bytes.fromhex(key_hex)

    # Initialize AES-GCM
    aesgcm = AESGCM(key)

    # Generate random nonce (12 bytes for GCM)
    nonce = os.urandom(12)

    # Read plaintext
    with open(input_path, 'rb') as f:
        plaintext = f.read()

    # Encrypt
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    # Write encrypted data
    with open(output_path, 'wb') as f:
        # Write nonce first (12 bytes)
        f.write(nonce)
        # Write ciphertext (includes authentication tag)
        f.write(ciphertext)

    return {
        'algorithm': 'AES-256-GCM',
        'nonce': nonce.hex(),
        'encrypted_size': len(ciphertext)
    }


def decrypt_file(input_path, output_path, key_hex):
    """
    Decrypt a file using AES-256-GCM.

    Args:
        input_path: Path to the encrypted file
        output_path: Path where decrypted file will be saved
        key_hex: Hex-encoded encryption key (64 characters)

    Returns:
        int: Size of decrypted data

    Raises:
        ValueError: If key is invalid or decryption fails
        FileNotFoundError: If input file doesn't exist
    """
    if len(key_hex) != 64:
        raise ValueError("Encryption key must be 64 hex characters (256 bits)")

    # Convert hex key to bytes
    key = bytes.fromhex(key_hex)

    # Initialize AES-GCM
    aesgcm = AESGCM(key)

    # Read encrypted data
    with open(input_path, 'rb') as f:
        # Read nonce (first 12 bytes)
        nonce = f.read(12)
        # Read ciphertext (rest of file)
        ciphertext = f.read()

    try:
        # Decrypt and verify authentication tag
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except Exception as e:
        raise ValueError(f"Decryption failed: {str(e)}")

    # Write decrypted data
    with open(output_path, 'wb') as f:
        f.write(plaintext)

    return len(plaintext)


def encrypt_data(data, key_hex):
    """
    Encrypt data in memory.

    Args:
        data: Bytes to encrypt
        key_hex: Hex-encoded encryption key

    Returns:
        tuple: (nonce, ciphertext)
    """
    if len(key_hex) != 64:
        raise ValueError("Encryption key must be 64 hex characters (256 bits)")

    key = bytes.fromhex(key_hex)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, data, None)

    return nonce, ciphertext


def decrypt_data(nonce, ciphertext, key_hex):
    """
    Decrypt data in memory.

    Args:
        nonce: Nonce bytes
        ciphertext: Encrypted data
        key_hex: Hex-encoded encryption key

    Returns:
        bytes: Decrypted data
    """
    if len(key_hex) != 64:
        raise ValueError("Encryption key must be 64 hex characters (256 bits)")

    key = bytes.fromhex(key_hex)
    aesgcm = AESGCM(key)

    return aesgcm.decrypt(nonce, ciphertext, None)
