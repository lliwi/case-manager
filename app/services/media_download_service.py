"""
Media Download Service for monitoring results.

Downloads and stores media files from social media posts with
forensic integrity guarantees (SHA-256 hashing).

Features:
- Download images and videos from URLs
- Calculate SHA-256 hash for integrity verification
- Store in organized directory structure
- Support for various media formats
"""
import os
import hashlib
import mimetypes
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import requests
from urllib.parse import urlparse
import uuid

from flask import current_app

logger = logging.getLogger(__name__)


class MediaDownloadService:
    """
    Service for downloading and storing media from monitoring results.

    Ensures forensic integrity with hash verification.
    """

    # Supported media types
    SUPPORTED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
    SUPPORTED_VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.webm', '.m4v'}

    # Download configuration
    DEFAULT_TIMEOUT = 30  # seconds
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    CHUNK_SIZE = 8192  # 8KB chunks

    # Directory structure
    MONITORING_MEDIA_FOLDER = 'monitoring'

    def __init__(self, base_path: Optional[str] = None):
        """
        Initialize the media download service.

        Args:
            base_path: Base path for media storage. If not provided,
                      uses EVIDENCE_FOLDER from app config.
        """
        self.base_path = base_path

    def _get_base_path(self) -> str:
        """Get the base path for media storage."""
        if self.base_path:
            return self.base_path

        try:
            return current_app.config.get('EVIDENCE_FOLDER', 'data/evidence')
        except RuntimeError:
            # Outside app context
            return 'data/evidence'

    def _get_storage_path(self, task_id: int, result_id: int) -> str:
        """
        Get the storage path for a monitoring result's media.

        Args:
            task_id: Monitoring task ID
            result_id: Monitoring result ID

        Returns:
            Full path to the media storage directory
        """
        base = self._get_base_path()
        path = os.path.join(
            base,
            self.MONITORING_MEDIA_FOLDER,
            f'task_{task_id}',
            f'result_{result_id}'
        )

        # Create directory if it doesn't exist
        os.makedirs(path, exist_ok=True)

        return path

    def download_media(
        self,
        urls: List[str],
        task_id: int,
        result_id: int
    ) -> List[Dict[str, Any]]:
        """
        Download media files to local storage.

        Args:
            urls: List of media URLs to download
            task_id: Monitoring task ID
            result_id: Monitoring result ID

        Returns:
            List of dicts with:
                - original_url: Original URL
                - local_path: Path to downloaded file
                - sha256_hash: SHA-256 hash of file
                - file_size: Size in bytes
                - mime_type: MIME type
                - success: Whether download succeeded
                - error: Error message if failed
        """
        results = []
        storage_path = self._get_storage_path(task_id, result_id)

        for i, url in enumerate(urls):
            result = self._download_single(url, storage_path, i)
            results.append(result)

        return results

    def _download_single(
        self,
        url: str,
        storage_path: str,
        index: int
    ) -> Dict[str, Any]:
        """
        Download a single media file.

        Args:
            url: URL to download
            storage_path: Directory to store the file
            index: Index for filename

        Returns:
            Download result dict
        """
        result = {
            'original_url': url,
            'local_path': None,
            'sha256_hash': None,
            'file_size': 0,
            'mime_type': None,
            'success': False,
            'error': None
        }

        try:
            # Parse URL to get extension
            parsed = urlparse(url)
            path_ext = os.path.splitext(parsed.path)[1].lower()

            # Make request with streaming
            response = requests.get(
                url,
                stream=True,
                timeout=self.DEFAULT_TIMEOUT,
                headers={'User-Agent': 'CaseManager-Monitoring/1.0'}
            )
            response.raise_for_status()

            # Get content type and determine extension
            content_type = response.headers.get('Content-Type', '')
            if content_type:
                mime_ext = mimetypes.guess_extension(content_type.split(';')[0])
            else:
                mime_ext = None

            # Use URL extension, then MIME extension, then default
            extension = path_ext or mime_ext or '.jpg'

            # Generate unique filename
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            unique_id = uuid.uuid4().hex[:8]
            filename = f'media_{index:03d}_{timestamp}_{unique_id}{extension}'
            local_path = os.path.join(storage_path, filename)

            # Download with size limit and hash calculation
            sha256 = hashlib.sha256()
            file_size = 0

            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=self.CHUNK_SIZE):
                    if chunk:
                        file_size += len(chunk)

                        if file_size > self.MAX_FILE_SIZE:
                            # File too large, abort
                            f.close()
                            os.remove(local_path)
                            result['error'] = f'Archivo demasiado grande (>{self.MAX_FILE_SIZE // (1024*1024)}MB)'
                            return result

                        f.write(chunk)
                        sha256.update(chunk)

            # Get MIME type
            mime_type, _ = mimetypes.guess_type(local_path)
            if not mime_type:
                mime_type = content_type.split(';')[0] if content_type else 'application/octet-stream'

            result.update({
                'local_path': local_path,
                'sha256_hash': sha256.hexdigest(),
                'file_size': file_size,
                'mime_type': mime_type,
                'success': True
            })

            logger.info(f"Downloaded media: {url} -> {local_path} ({file_size} bytes)")

        except requests.exceptions.Timeout:
            result['error'] = 'Timeout al descargar el archivo'
            logger.warning(f"Timeout downloading {url}")

        except requests.exceptions.HTTPError as e:
            result['error'] = f'Error HTTP: {e.response.status_code}'
            logger.warning(f"HTTP error downloading {url}: {e}")

        except requests.exceptions.RequestException as e:
            result['error'] = f'Error de conexión: {str(e)}'
            logger.warning(f"Request error downloading {url}: {e}")

        except IOError as e:
            result['error'] = f'Error de escritura: {str(e)}'
            logger.error(f"IO error saving {url}: {e}")

        except Exception as e:
            result['error'] = f'Error inesperado: {str(e)}'
            logger.error(f"Unexpected error downloading {url}: {e}", exc_info=True)

        return result

    def get_media_for_analysis(
        self,
        local_paths: List[str],
        as_base64: bool = True
    ) -> List[str]:
        """
        Get media files ready for AI analysis.

        Args:
            local_paths: Paths to local media files
            as_base64: If True, return base64 encoded data URIs.
                      If False, return file paths.

        Returns:
            List of base64 data URIs or file paths
        """
        result = []

        for path in local_paths:
            if not os.path.exists(path):
                logger.warning(f"Media file not found: {path}")
                continue

            if as_base64:
                try:
                    encoded = self._encode_file_as_base64(path)
                    if encoded:
                        result.append(encoded)
                except Exception as e:
                    logger.error(f"Error encoding {path}: {e}")
            else:
                result.append(path)

        return result

    def _encode_file_as_base64(self, file_path: str) -> Optional[str]:
        """
        Encode a file as base64 with data URI.

        Args:
            file_path: Path to file

        Returns:
            Base64 data URI string or None if error
        """
        import base64

        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = 'application/octet-stream'

        with open(file_path, 'rb') as f:
            data = base64.b64encode(f.read()).decode('utf-8')

        return f'data:{mime_type};base64,{data}'

    def verify_file_integrity(self, file_path: str, expected_hash: str) -> bool:
        """
        Verify file integrity by comparing SHA-256 hash.

        Args:
            file_path: Path to file
            expected_hash: Expected SHA-256 hash

        Returns:
            True if hash matches, False otherwise
        """
        if not os.path.exists(file_path):
            return False

        sha256 = hashlib.sha256()

        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(self.CHUNK_SIZE), b''):
                sha256.update(chunk)

        return sha256.hexdigest() == expected_hash

    def calculate_file_hash(self, file_path: str) -> Optional[str]:
        """
        Calculate SHA-256 hash of a file.

        Args:
            file_path: Path to file

        Returns:
            SHA-256 hash string or None if error
        """
        if not os.path.exists(file_path):
            return None

        sha256 = hashlib.sha256()

        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(self.CHUNK_SIZE), b''):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {e}")
            return None

    def cleanup_result_media(self, task_id: int, result_id: int) -> bool:
        """
        Remove all media files for a monitoring result.

        Args:
            task_id: Monitoring task ID
            result_id: Monitoring result ID

        Returns:
            True if cleanup succeeded
        """
        import shutil

        storage_path = self._get_storage_path(task_id, result_id)

        try:
            if os.path.exists(storage_path):
                shutil.rmtree(storage_path)
                logger.info(f"Cleaned up media for task {task_id}, result {result_id}")
            return True
        except Exception as e:
            logger.error(f"Error cleaning up media: {e}")
            return False

    def get_storage_stats(self, task_id: int) -> Dict[str, Any]:
        """
        Get storage statistics for a monitoring task.

        Args:
            task_id: Monitoring task ID

        Returns:
            Dict with storage statistics
        """
        base = self._get_base_path()
        task_path = os.path.join(base, self.MONITORING_MEDIA_FOLDER, f'task_{task_id}')

        stats = {
            'task_id': task_id,
            'total_size_bytes': 0,
            'file_count': 0,
            'result_count': 0
        }

        if not os.path.exists(task_path):
            return stats

        for result_dir in os.listdir(task_path):
            result_path = os.path.join(task_path, result_dir)
            if os.path.isdir(result_path):
                stats['result_count'] += 1

                for filename in os.listdir(result_path):
                    file_path = os.path.join(result_path, filename)
                    if os.path.isfile(file_path):
                        stats['file_count'] += 1
                        stats['total_size_bytes'] += os.path.getsize(file_path)

        stats['total_size_mb'] = round(stats['total_size_bytes'] / (1024 * 1024), 2)

        return stats
