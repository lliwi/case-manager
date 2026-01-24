"""
Backup Service for creating complete system backups.

Creates ZIP archives containing:
- PostgreSQL database dump
- Evidence files (encrypted)
- Uploaded files
- Export files
- Reports
- Monitoring media (OSINT downloads)
- API Keys configuration
- Environment configuration (.env)

Compliant with forensic requirements for evidence preservation.
"""
import os
import json
import shutil
import subprocess
import tempfile
import zipfile
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional, List
from flask import current_app
from app.extensions import db
from app.models.api_key import ApiKey
from app.models.user import User
from app.models.case import Case
from app.models.evidence import Evidence
from app.models.audit import AuditLog


class BackupService:
    """Service for creating and managing system backups."""

    BACKUP_VERSION = "1.0"

    def __init__(self, backup_folder: Optional[str] = None):
        """
        Initialize backup service.

        Args:
            backup_folder: Directory to store backups. Defaults to data/backups.
        """
        self.backup_folder = backup_folder or self._get_backup_folder()
        os.makedirs(self.backup_folder, exist_ok=True)

    def _get_backup_folder(self) -> str:
        """Get the backup folder path from config or default."""
        try:
            base = current_app.config.get('UPLOAD_FOLDER', 'data/uploads')
            return os.path.join(os.path.dirname(base), 'backups')
        except RuntimeError:
            return os.path.join(os.getcwd(), 'data', 'backups')

    def _get_data_folders(self) -> Dict[str, str]:
        """Get all data folder paths."""
        try:
            base = os.path.dirname(current_app.config.get('UPLOAD_FOLDER', 'data/uploads'))
        except RuntimeError:
            base = os.path.join(os.getcwd(), 'data')

        return {
            'evidence': os.path.join(base, 'evidence'),
            'uploads': os.path.join(base, 'uploads'),
            'exports': os.path.join(base, 'exports'),
            'reports': os.path.join(base, 'reports'),
        }

    def _get_project_root(self) -> str:
        """Get project root directory."""
        try:
            return os.path.dirname(current_app.root_path)
        except RuntimeError:
            return os.getcwd()

    def _calculate_file_hash(self, filepath: str) -> str:
        """Calculate SHA-256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _dump_database(self, output_path: str) -> Dict[str, Any]:
        """
        Dump PostgreSQL database to SQL file.

        Args:
            output_path: Path to save the database dump.

        Returns:
            Dict with dump info and status.
        """
        result = {
            'success': False,
            'file': output_path,
            'size': 0,
            'tables': 0,
            'error': None
        }

        try:
            # Get database connection info from environment
            db_url = os.environ.get('DATABASE_URL', '')

            if not db_url:
                result['error'] = 'DATABASE_URL not configured'
                return result

            # Parse DATABASE_URL
            # Format: postgresql://user:password@host:port/dbname
            import urllib.parse
            parsed = urllib.parse.urlparse(db_url)

            db_host = parsed.hostname or 'localhost'
            db_port = str(parsed.port or 5432)
            db_name = parsed.path.lstrip('/')
            db_user = parsed.username or 'postgres'
            db_password = parsed.password or ''

            # Set password in environment for pg_dump
            env = os.environ.copy()
            env['PGPASSWORD'] = db_password

            # Run pg_dump
            cmd = [
                'pg_dump',
                '-h', db_host,
                '-p', db_port,
                '-U', db_user,
                '-d', db_name,
                '-F', 'p',  # Plain text format
                '--no-owner',
                '--no-acl',
                '-f', output_path
            ]

            process = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if process.returncode != 0:
                result['error'] = process.stderr
                return result

            # Get file info
            if os.path.exists(output_path):
                result['success'] = True
                result['size'] = os.path.getsize(output_path)
                result['hash'] = self._calculate_file_hash(output_path)

                # Count tables in dump
                with open(output_path, 'r') as f:
                    content = f.read()
                    result['tables'] = content.count('CREATE TABLE')

        except subprocess.TimeoutExpired:
            result['error'] = 'Database dump timed out (5 minutes)'
        except FileNotFoundError:
            result['error'] = 'pg_dump not found. Is PostgreSQL client installed?'
        except Exception as e:
            result['error'] = str(e)

        return result

    def _export_api_keys(self, output_path: str) -> Dict[str, Any]:
        """
        Export API keys to JSON file (decrypted).

        Args:
            output_path: Path to save the API keys.

        Returns:
            Dict with export info and status.
        """
        result = {
            'success': False,
            'file': output_path,
            'count': 0,
            'error': None
        }

        try:
            api_keys = ApiKey.query.filter_by(is_deleted=False).all()

            keys_data = []
            for key in api_keys:
                keys_data.append({
                    'service_name': key.service_name,
                    'key_name': key.key_name,
                    'api_key': key.get_api_key(),  # Decrypted
                    'description': key.description,
                    'is_active': key.is_active,
                    'created_at': key.created_at.isoformat() if key.created_at else None,
                    'last_used_at': key.last_used_at.isoformat() if key.last_used_at else None,
                    'usage_count': key.usage_count
                })

            with open(output_path, 'w') as f:
                json.dump({
                    'exported_at': datetime.utcnow().isoformat(),
                    'total_keys': len(keys_data),
                    'keys': keys_data
                }, f, indent=2)

            result['success'] = True
            result['count'] = len(keys_data)
            result['hash'] = self._calculate_file_hash(output_path)

        except Exception as e:
            result['error'] = str(e)

        return result

    def _export_statistics(self, output_path: str) -> Dict[str, Any]:
        """
        Export system statistics to JSON file.

        Args:
            output_path: Path to save the statistics.

        Returns:
            Dict with export info and status.
        """
        result = {
            'success': False,
            'file': output_path,
            'error': None
        }

        try:
            stats = {
                'exported_at': datetime.utcnow().isoformat(),
                'users': {
                    'total': User.query.count(),
                    'active': User.query.filter_by(is_active=True).count()
                },
                'cases': {
                    'total': Case.query.filter_by(is_deleted=False).count()
                },
                'evidence': {
                    'total': Evidence.query.filter_by(is_deleted=False).count()
                },
                'audit_logs': {
                    'total': AuditLog.query.count()
                }
            }

            with open(output_path, 'w') as f:
                json.dump(stats, f, indent=2)

            result['success'] = True
            result['stats'] = stats

        except Exception as e:
            result['error'] = str(e)

        return result

    def _copy_folder(
        self,
        source: str,
        dest: str,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Copy a folder recursively with file tracking.

        Args:
            source: Source folder path.
            dest: Destination folder path.
            progress_callback: Optional callback for progress updates.

        Returns:
            Dict with copy info and status.
        """
        result = {
            'success': False,
            'source': source,
            'dest': dest,
            'files_copied': 0,
            'total_size': 0,
            'errors': [],
            'files': []
        }

        if not os.path.exists(source):
            result['success'] = True  # Nothing to copy is not an error
            return result

        try:
            os.makedirs(dest, exist_ok=True)

            for root, dirs, files in os.walk(source):
                # Calculate relative path
                rel_path = os.path.relpath(root, source)
                dest_dir = os.path.join(dest, rel_path)

                # Create directory structure
                os.makedirs(dest_dir, exist_ok=True)

                for filename in files:
                    src_file = os.path.join(root, filename)
                    dst_file = os.path.join(dest_dir, filename)

                    try:
                        shutil.copy2(src_file, dst_file)
                        file_size = os.path.getsize(src_file)
                        result['files_copied'] += 1
                        result['total_size'] += file_size
                        result['files'].append({
                            'path': os.path.relpath(src_file, source),
                            'size': file_size
                        })

                        if progress_callback:
                            progress_callback(result['files_copied'], filename)

                    except Exception as e:
                        result['errors'].append(f"{src_file}: {str(e)}")

            result['success'] = len(result['errors']) == 0

        except Exception as e:
            result['errors'].append(str(e))

        return result

    def _copy_env_file(self, dest_path: str) -> Dict[str, Any]:
        """
        Copy .env file to backup.

        Args:
            dest_path: Destination path for .env file.

        Returns:
            Dict with copy info and status.
        """
        result = {
            'success': False,
            'file': dest_path,
            'error': None
        }

        try:
            project_root = self._get_project_root()
            env_path = os.path.join(project_root, '.env')

            if os.path.exists(env_path):
                shutil.copy2(env_path, dest_path)
                result['success'] = True
                result['hash'] = self._calculate_file_hash(dest_path)
            else:
                result['error'] = '.env file not found'

        except Exception as e:
            result['error'] = str(e)

        return result

    def create_backup(
        self,
        include_database: bool = True,
        include_evidence: bool = True,
        include_uploads: bool = True,
        include_exports: bool = True,
        include_reports: bool = True,
        include_api_keys: bool = True,
        include_env: bool = True,
        created_by: Optional[User] = None,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Create a complete system backup.

        Args:
            include_database: Include PostgreSQL database dump.
            include_evidence: Include evidence files.
            include_uploads: Include uploaded files.
            include_exports: Include export files.
            include_reports: Include report files.
            include_api_keys: Include API keys (decrypted).
            include_env: Include .env configuration.
            created_by: User creating the backup.
            progress_callback: Optional callback for progress updates.

        Returns:
            Dict with backup info and status.
        """
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        backup_name = f'backup_{timestamp}'

        result = {
            'success': False,
            'backup_name': backup_name,
            'created_at': datetime.utcnow().isoformat(),
            'created_by': created_by.email if created_by else 'system',
            'zip_file': None,
            'zip_size': 0,
            'zip_hash': None,
            'components': {},
            'manifest': {},
            'errors': []
        }

        # Create temporary directory for backup assembly
        temp_dir = tempfile.mkdtemp(prefix='backup_')
        backup_dir = os.path.join(temp_dir, backup_name)
        os.makedirs(backup_dir)

        try:
            data_folders = self._get_data_folders()

            # 1. Database dump
            if include_database:
                if progress_callback:
                    progress_callback('database', 'Exportando base de datos...')

                db_path = os.path.join(backup_dir, 'database.sql')
                db_result = self._dump_database(db_path)
                result['components']['database'] = db_result

                if not db_result['success']:
                    result['errors'].append(f"Database: {db_result['error']}")

            # 2. Evidence files
            if include_evidence:
                if progress_callback:
                    progress_callback('evidence', 'Copiando evidencias...')

                evidence_dest = os.path.join(backup_dir, 'evidence')
                evidence_result = self._copy_folder(
                    data_folders['evidence'],
                    evidence_dest,
                    progress_callback
                )
                result['components']['evidence'] = {
                    'success': evidence_result['success'],
                    'files_count': evidence_result['files_copied'],
                    'total_size': evidence_result['total_size'],
                    'errors': evidence_result['errors']
                }

            # 3. Uploads
            if include_uploads:
                if progress_callback:
                    progress_callback('uploads', 'Copiando uploads...')

                uploads_dest = os.path.join(backup_dir, 'uploads')
                uploads_result = self._copy_folder(
                    data_folders['uploads'],
                    uploads_dest
                )
                result['components']['uploads'] = {
                    'success': uploads_result['success'],
                    'files_count': uploads_result['files_copied'],
                    'total_size': uploads_result['total_size'],
                    'errors': uploads_result['errors']
                }

            # 4. Exports
            if include_exports:
                if progress_callback:
                    progress_callback('exports', 'Copiando exports...')

                exports_dest = os.path.join(backup_dir, 'exports')
                exports_result = self._copy_folder(
                    data_folders['exports'],
                    exports_dest
                )
                result['components']['exports'] = {
                    'success': exports_result['success'],
                    'files_count': exports_result['files_copied'],
                    'total_size': exports_result['total_size'],
                    'errors': exports_result['errors']
                }

            # 5. Reports
            if include_reports:
                if progress_callback:
                    progress_callback('reports', 'Copiando informes...')

                reports_dest = os.path.join(backup_dir, 'reports')
                reports_result = self._copy_folder(
                    data_folders['reports'],
                    reports_dest
                )
                result['components']['reports'] = {
                    'success': reports_result['success'],
                    'files_count': reports_result['files_copied'],
                    'total_size': reports_result['total_size'],
                    'errors': reports_result['errors']
                }

            # 6. API Keys
            if include_api_keys:
                if progress_callback:
                    progress_callback('api_keys', 'Exportando API Keys...')

                api_keys_path = os.path.join(backup_dir, 'api_keys.json')
                api_keys_result = self._export_api_keys(api_keys_path)
                result['components']['api_keys'] = api_keys_result

            # 7. Environment configuration
            if include_env:
                if progress_callback:
                    progress_callback('env', 'Copiando configuración...')

                env_path = os.path.join(backup_dir, 'env_backup')
                env_result = self._copy_env_file(env_path)
                result['components']['env'] = env_result

            # 8. Statistics
            if progress_callback:
                progress_callback('stats', 'Generando estadísticas...')

            stats_path = os.path.join(backup_dir, 'statistics.json')
            stats_result = self._export_statistics(stats_path)
            result['components']['statistics'] = stats_result

            # 9. Create manifest
            manifest = {
                'version': self.BACKUP_VERSION,
                'created_at': result['created_at'],
                'created_by': result['created_by'],
                'components': list(result['components'].keys()),
                'component_details': result['components']
            }

            manifest_path = os.path.join(backup_dir, 'manifest.json')
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2, default=str)

            result['manifest'] = manifest

            # 10. Create ZIP archive
            if progress_callback:
                progress_callback('zip', 'Creando archivo ZIP...')

            zip_filename = f'{backup_name}.zip'
            zip_path = os.path.join(self.backup_folder, zip_filename)

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(backup_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, temp_dir)
                        zipf.write(file_path, arcname)

            result['zip_file'] = zip_path
            result['zip_size'] = os.path.getsize(zip_path)
            result['zip_hash'] = self._calculate_file_hash(zip_path)
            result['success'] = True

        except Exception as e:
            result['errors'].append(str(e))

        finally:
            # Cleanup temporary directory
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass

        return result

    def list_backups(self) -> List[Dict[str, Any]]:
        """
        List all available backups.

        Returns:
            List of backup info dictionaries.
        """
        backups = []

        if not os.path.exists(self.backup_folder):
            return backups

        for filename in os.listdir(self.backup_folder):
            if filename.endswith('.zip') and filename.startswith('backup_'):
                filepath = os.path.join(self.backup_folder, filename)

                # Parse timestamp from filename
                try:
                    timestamp_str = filename.replace('backup_', '').replace('.zip', '')
                    created_at = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                except ValueError:
                    created_at = datetime.fromtimestamp(os.path.getctime(filepath))

                backups.append({
                    'filename': filename,
                    'filepath': filepath,
                    'size': os.path.getsize(filepath),
                    'created_at': created_at,
                    'hash': self._calculate_file_hash(filepath)
                })

        # Sort by creation date (newest first)
        backups.sort(key=lambda x: x['created_at'], reverse=True)

        return backups

    def delete_backup(self, filename: str) -> Dict[str, Any]:
        """
        Delete a backup file.

        Args:
            filename: Name of the backup file to delete.

        Returns:
            Dict with deletion status.
        """
        result = {
            'success': False,
            'filename': filename,
            'error': None
        }

        try:
            filepath = os.path.join(self.backup_folder, filename)

            if not os.path.exists(filepath):
                result['error'] = 'Backup file not found'
                return result

            if not filename.endswith('.zip') or not filename.startswith('backup_'):
                result['error'] = 'Invalid backup filename'
                return result

            os.remove(filepath)
            result['success'] = True

        except Exception as e:
            result['error'] = str(e)

        return result

    def get_backup_info(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed info about a backup by reading its manifest.

        Args:
            filename: Name of the backup file.

        Returns:
            Dict with backup info or None if not found.
        """
        filepath = os.path.join(self.backup_folder, filename)

        if not os.path.exists(filepath):
            return None

        try:
            with zipfile.ZipFile(filepath, 'r') as zipf:
                # Find and read manifest
                manifest_name = None
                for name in zipf.namelist():
                    if name.endswith('manifest.json'):
                        manifest_name = name
                        break

                if manifest_name:
                    with zipf.open(manifest_name) as f:
                        manifest = json.load(f)
                        return {
                            'filename': filename,
                            'filepath': filepath,
                            'size': os.path.getsize(filepath),
                            'manifest': manifest
                        }
        except Exception:
            pass

        return {
            'filename': filename,
            'filepath': filepath,
            'size': os.path.getsize(filepath),
            'manifest': None
        }
