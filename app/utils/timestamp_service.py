"""
Cryptographic Timestamp Service for forensic integrity.

This module provides cryptographic proof of when records were created,
ensuring compliance with UNE 71506 forensic standards.

The timestamp signature is created using HMAC-SHA256 with the following data:
- Record content hash
- UTC timestamp
- Server secret key

This provides non-repudiation: the timestamp cannot be forged without access
to the secret key, and any modification to the record invalidates the signature.
"""
import hashlib
import hmac
import json
from datetime import datetime
from flask import current_app


class TimestampService:
    """Service for creating and verifying cryptographic timestamps."""

    @staticmethod
    def _get_signing_key():
        """Get the signing key from config."""
        key = current_app.config.get('SECRET_KEY', 'default-key')
        # Derive a specific key for timestamps
        return hashlib.sha256(f"timestamp-{key}".encode()).digest()

    @staticmethod
    def create_record_hash(data: dict) -> str:
        """
        Create a SHA-256 hash of the record data.

        Args:
            data: Dictionary containing the record fields to hash

        Returns:
            Hexadecimal hash string
        """
        # Sort keys for consistent hashing
        normalized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(normalized.encode()).hexdigest()

    @staticmethod
    def create_timestamp_signature(record_hash: str, timestamp: datetime) -> str:
        """
        Create a cryptographic signature proving the timestamp.

        Args:
            record_hash: SHA-256 hash of the record content
            timestamp: UTC datetime of record creation

        Returns:
            HMAC-SHA256 signature (hexadecimal)
        """
        key = TimestampService._get_signing_key()
        # Combine hash and timestamp for signing
        message = f"{record_hash}|{timestamp.isoformat()}".encode()
        signature = hmac.new(key, message, hashlib.sha256).hexdigest()
        return signature

    @staticmethod
    def verify_timestamp_signature(record_hash: str, timestamp: datetime, signature: str) -> bool:
        """
        Verify that a timestamp signature is valid.

        Args:
            record_hash: SHA-256 hash of the record content
            timestamp: UTC datetime claimed for record creation
            signature: HMAC signature to verify

        Returns:
            True if signature is valid, False otherwise
        """
        expected = TimestampService.create_timestamp_signature(record_hash, timestamp)
        return hmac.compare_digest(expected, signature)

    @staticmethod
    def sign_audit_log(audit_log) -> tuple[str, str]:
        """
        Create cryptographic timestamp for an audit log entry.

        Args:
            audit_log: AuditLog model instance

        Returns:
            Tuple of (record_hash, timestamp_signature)
        """
        # Fields that define the audit record
        data = {
            'action': audit_log.action,
            'resource_type': audit_log.resource_type,
            'resource_id': audit_log.resource_id,
            'description': audit_log.description,
            'user_id': audit_log.user_id,
            'user_email': audit_log.user_email,
            'ip_address': audit_log.ip_address,
            'timestamp': audit_log.timestamp.isoformat() if audit_log.timestamp else None,
        }

        record_hash = TimestampService.create_record_hash(data)
        signature = TimestampService.create_timestamp_signature(record_hash, audit_log.timestamp)

        return record_hash, signature

    @staticmethod
    def sign_chain_of_custody(custody_entry) -> tuple[str, str]:
        """
        Create cryptographic timestamp for a chain of custody entry.

        Args:
            custody_entry: ChainOfCustody model instance

        Returns:
            Tuple of (record_hash, timestamp_signature)
        """
        # Fields that define the custody record
        data = {
            'evidence_id': custody_entry.evidence_id,
            'action': custody_entry.action,
            'user_id': custody_entry.user_id,
            'timestamp': custody_entry.timestamp.isoformat() if custody_entry.timestamp else None,
            'ip_address': custody_entry.ip_address,
            'notes': custody_entry.notes,
            'hash_verified': custody_entry.hash_verified,
            'hash_match': custody_entry.hash_match,
        }

        record_hash = TimestampService.create_record_hash(data)
        signature = TimestampService.create_timestamp_signature(record_hash, custody_entry.timestamp)

        return record_hash, signature

    @staticmethod
    def verify_audit_log(audit_log) -> dict:
        """
        Verify the integrity of an audit log entry.

        Args:
            audit_log: AuditLog model instance with timestamp_signature

        Returns:
            Dictionary with verification results
        """
        if not audit_log.timestamp_signature or not audit_log.record_hash:
            return {
                'valid': False,
                'error': 'No timestamp signature found',
                'signed': False
            }

        # Recalculate hash
        data = {
            'action': audit_log.action,
            'resource_type': audit_log.resource_type,
            'resource_id': audit_log.resource_id,
            'description': audit_log.description,
            'user_id': audit_log.user_id,
            'user_email': audit_log.user_email,
            'ip_address': audit_log.ip_address,
            'timestamp': audit_log.timestamp.isoformat() if audit_log.timestamp else None,
        }

        current_hash = TimestampService.create_record_hash(data)

        # Check if record has been modified
        if current_hash != audit_log.record_hash:
            return {
                'valid': False,
                'error': 'Record hash mismatch - data may have been tampered',
                'signed': True,
                'original_hash': audit_log.record_hash,
                'current_hash': current_hash
            }

        # Verify signature
        signature_valid = TimestampService.verify_timestamp_signature(
            audit_log.record_hash,
            audit_log.timestamp,
            audit_log.timestamp_signature
        )

        return {
            'valid': signature_valid,
            'signed': True,
            'error': None if signature_valid else 'Signature verification failed',
            'record_hash': audit_log.record_hash,
            'timestamp': audit_log.timestamp.isoformat()
        }

    @staticmethod
    def verify_chain_of_custody(custody_entry) -> dict:
        """
        Verify the integrity of a chain of custody entry.

        Args:
            custody_entry: ChainOfCustody model instance with timestamp_signature

        Returns:
            Dictionary with verification results
        """
        if not custody_entry.timestamp_signature or not custody_entry.record_hash:
            return {
                'valid': False,
                'error': 'No timestamp signature found',
                'signed': False
            }

        # Recalculate hash
        data = {
            'evidence_id': custody_entry.evidence_id,
            'action': custody_entry.action,
            'user_id': custody_entry.user_id,
            'timestamp': custody_entry.timestamp.isoformat() if custody_entry.timestamp else None,
            'ip_address': custody_entry.ip_address,
            'notes': custody_entry.notes,
            'hash_verified': custody_entry.hash_verified,
            'hash_match': custody_entry.hash_match,
        }

        current_hash = TimestampService.create_record_hash(data)

        # Check if record has been modified
        if current_hash != custody_entry.record_hash:
            return {
                'valid': False,
                'error': 'Record hash mismatch - data may have been tampered',
                'signed': True,
                'original_hash': custody_entry.record_hash,
                'current_hash': current_hash
            }

        # Verify signature
        signature_valid = TimestampService.verify_timestamp_signature(
            custody_entry.record_hash,
            custody_entry.timestamp,
            custody_entry.timestamp_signature
        )

        return {
            'valid': signature_valid,
            'signed': True,
            'error': None if signature_valid else 'Signature verification failed',
            'record_hash': custody_entry.record_hash,
            'timestamp': custody_entry.timestamp.isoformat()
        }
