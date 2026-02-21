"""
Application configuration classes.
"""
import os
from datetime import timedelta


class Config:
    """Base configuration."""

    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://postgres:postgres@localhost:5432/case_manager'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Database connection pool settings
    _base_engine_options = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_size': 10,
        'max_overflow': 20,
    }

    # Add SSL/TLS options if enabled
    DATABASE_SSL_MODE = os.environ.get('DATABASE_SSL_MODE', 'prefer')  # disable, allow, prefer, require, verify-ca, verify-full
    if DATABASE_SSL_MODE and DATABASE_SSL_MODE != 'disable':
        _base_engine_options['connect_args'] = {
            'sslmode': DATABASE_SSL_MODE,
        }
        # Optional: specify certificate paths for verify-ca/verify-full modes
        ssl_ca = os.environ.get('DATABASE_SSL_CA')
        ssl_cert = os.environ.get('DATABASE_SSL_CERT')
        ssl_key = os.environ.get('DATABASE_SSL_KEY')
        if ssl_ca:
            _base_engine_options['connect_args']['sslrootcert'] = ssl_ca
        if ssl_cert:
            _base_engine_options['connect_args']['sslcert'] = ssl_cert
        if ssl_key:
            _base_engine_options['connect_args']['sslkey'] = ssl_key

    SQLALCHEMY_ENGINE_OPTIONS = _base_engine_options

    # Neo4j
    NEO4J_URI = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
    NEO4J_USER = os.environ.get('NEO4J_USER', 'neo4j')
    NEO4J_PASSWORD = os.environ.get('NEO4J_PASSWORD')

    # Redis/Celery
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')

    # Security
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None
    BCRYPT_LOG_ROUNDS = 12

    # Rate limiting (using Redis as storage backend)
    RATELIMIT_STORAGE_URI = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    RATELIMIT_DEFAULT = "200 per day, 50 per hour"

    # File uploads
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB max file size
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'data', 'uploads')
    EVIDENCE_FOLDER = os.path.join(os.getcwd(), 'data', 'evidence')
    EXPORT_FOLDER = os.path.join(os.getcwd(), 'data', 'exports')
    REPORTS_PATH = os.path.join(os.getcwd(), 'data', 'reports')
    ALLOWED_EVIDENCE_EXTENSIONS = {
        'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff',  # Images
        'mp4', 'avi', 'mov', 'mkv', 'flv',  # Video
        'mp3', 'wav', 'aac', 'flac',  # Audio
        'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',  # Documents
        'txt', 'csv', 'json', 'xml',  # Data files
        'zip', 'rar', '7z', 'tar', 'gz',  # Archives
        'eml', 'msg',  # Email
        'html', 'htm', 'mht',  # Web
    }

    # Evidence encryption
    EVIDENCE_ENCRYPTION_KEY = os.environ.get('EVIDENCE_ENCRYPTION_KEY')

    # Plugin system
    PLUGIN_FOLDER = os.path.join(os.getcwd(), 'app', 'plugins')

    # Public URL of this application (required for reverse image search plugin).
    # Must be a publicly reachable HTTPS/HTTP URL, e.g. https://investigation.example.com
    # If empty or pointing to localhost the reverse image search plugin is disabled.
    APP_PUBLIC_URL = os.environ.get('APP_PUBLIC_URL', '').rstrip('/')

    # Timestamp service
    TIMESTAMP_SERVICE_URL = os.environ.get('TIMESTAMP_SERVICE_URL')

    # Logging
    LOG_TO_STDOUT = os.environ.get('LOG_TO_STDOUT', False)
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False  # Allow HTTP in development
    BCRYPT_LOG_ROUNDS = 4  # Faster hashing in development


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {}  # SQLite doesn't support pool options
    BCRYPT_LOG_ROUNDS = 4
    SESSION_COOKIE_SECURE = False


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
