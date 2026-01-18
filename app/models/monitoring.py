"""
Monitoring models for social media surveillance.

This module implements periodic monitoring of social media accounts,
hashtags, and search queries with AI-powered analysis capabilities.

Features:
- Multiple data sources per monitoring task
- AI analysis with DeepSeek/OpenAI for image/content analysis
- Forensic integrity with SHA-256 hashing
- Audit logging for legal compliance
"""
from datetime import datetime
from app.extensions import db
from sqlalchemy import Enum as SQLAlchemyEnum
from enum import Enum
import hashlib


class MonitoringStatus(Enum):
    """Monitoring task status."""
    DRAFT = 'Borrador'           # Configuration in progress
    ACTIVE = 'Activo'            # Running periodic checks
    PAUSED = 'Pausado'           # Temporarily stopped
    COMPLETED = 'Completado'     # Task finished
    ARCHIVED = 'Archivado'       # Archived for reference


class SourcePlatform(Enum):
    """Supported social media platforms."""
    X_TWITTER = 'X (Twitter)'
    INSTAGRAM = 'Instagram'
    # Future platforms can be added here
    # FACEBOOK = 'Facebook'
    # TIKTOK = 'TikTok'


class SourceQueryType(Enum):
    """Types of queries for monitoring."""
    USER_PROFILE = 'Perfil de Usuario'     # Monitor a specific user
    HASHTAG = 'Hashtag'                     # Monitor a hashtag
    SEARCH_QUERY = 'Búsqueda'              # Monitor search results


class AIProvider(Enum):
    """AI providers for content analysis."""
    DEEPSEEK = 'deepseek'
    OPENAI = 'openai'


class MonitoringTask(db.Model):
    """
    Main monitoring task configuration linked to a Case.

    A monitoring task defines what to monitor (via MonitoringSource),
    how often to check, and what objective to detect using AI analysis.
    """
    __tablename__ = 'monitoring_tasks'

    # Primary key
    id = db.Column(db.Integer, primary_key=True)

    # Case relationship
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), nullable=False, index=True)

    # Task identification
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    # Monitoring objective (the question/condition to detect)
    # e.g., "Detectar actividades incompatibles con baja laboral"
    # e.g., "Detectar comportamiento violento o accidentes"
    monitoring_objective = db.Column(db.Text, nullable=False)

    # AI Analysis configuration
    ai_provider = db.Column(SQLAlchemyEnum(AIProvider), default=AIProvider.DEEPSEEK, nullable=False)
    ai_analysis_enabled = db.Column(db.Boolean, default=True, nullable=False)
    ai_prompt_template = db.Column(db.Text)  # Custom prompt for AI analysis (optional)

    # Scheduling
    check_interval_minutes = db.Column(db.Integer, default=60, nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime)  # Optional end date
    last_check_at = db.Column(db.DateTime)
    next_check_at = db.Column(db.DateTime, index=True)

    # Status
    status = db.Column(SQLAlchemyEnum(MonitoringStatus), default=MonitoringStatus.DRAFT, nullable=False, index=True)

    # Statistics
    total_checks = db.Column(db.Integer, default=0, nullable=False)
    total_results = db.Column(db.Integer, default=0, nullable=False)
    alerts_count = db.Column(db.Integer, default=0, nullable=False)  # Results flagged by AI
    unread_alerts_count = db.Column(db.Integer, default=0, nullable=False)  # For in-app notifications

    # Ownership
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Soft delete
    is_deleted = db.Column(db.Boolean, default=False, nullable=False, index=True)
    deleted_at = db.Column(db.DateTime)
    deleted_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Relationships
    case = db.relationship('Case', backref=db.backref('monitoring_tasks', lazy='dynamic'))
    created_by = db.relationship('User', foreign_keys=[created_by_id], backref='created_monitoring_tasks')
    deleted_by = db.relationship('User', foreign_keys=[deleted_by_id])
    sources = db.relationship('MonitoringSource', backref='task', lazy='dynamic',
                             cascade='all, delete-orphan', passive_deletes=True)
    results = db.relationship('MonitoringResult', backref='task', lazy='dynamic',
                             cascade='all, delete-orphan', passive_deletes=True)
    check_logs = db.relationship('MonitoringCheckLog', backref='task', lazy='dynamic',
                                cascade='all, delete-orphan', passive_deletes=True)

    def __repr__(self):
        return f'<MonitoringTask {self.id}: {self.name}>'

    def activate(self):
        """Activate the monitoring task."""
        if self.status in (MonitoringStatus.DRAFT, MonitoringStatus.PAUSED):
            self.status = MonitoringStatus.ACTIVE
            self.calculate_next_check()
            return True
        return False

    def pause(self):
        """Pause the monitoring task."""
        if self.status == MonitoringStatus.ACTIVE:
            self.status = MonitoringStatus.PAUSED
            return True
        return False

    def complete(self):
        """Mark the monitoring task as completed."""
        self.status = MonitoringStatus.COMPLETED
        self.next_check_at = None

    def calculate_next_check(self):
        """Calculate the next check time based on interval."""
        from datetime import timedelta

        now = datetime.utcnow()

        # If start_date is in the future, use that
        if self.start_date > now:
            self.next_check_at = self.start_date
        else:
            self.next_check_at = now + timedelta(minutes=self.check_interval_minutes)

        # Don't schedule past end_date
        if self.end_date and self.next_check_at > self.end_date:
            self.complete()

    def is_due_for_check(self):
        """Check if the task is due for a monitoring check."""
        if self.status != MonitoringStatus.ACTIVE:
            return False
        if self.next_check_at is None:
            return False
        return datetime.utcnow() >= self.next_check_at

    def increment_alerts(self, count=1):
        """Increment alert counters."""
        self.alerts_count += count
        self.unread_alerts_count += count

    def mark_alerts_read(self):
        """Mark all alerts as read."""
        self.unread_alerts_count = 0

    def soft_delete(self, user_id):
        """Soft delete the task."""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        self.deleted_by_id = user_id
        self.status = MonitoringStatus.ARCHIVED

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'case_id': self.case_id,
            'name': self.name,
            'description': self.description,
            'monitoring_objective': self.monitoring_objective,
            'ai_provider': self.ai_provider.value if self.ai_provider else None,
            'ai_analysis_enabled': self.ai_analysis_enabled,
            'check_interval_minutes': self.check_interval_minutes,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'status': self.status.value if self.status else None,
            'total_checks': self.total_checks,
            'total_results': self.total_results,
            'alerts_count': self.alerts_count,
            'unread_alerts_count': self.unread_alerts_count,
            'last_check_at': self.last_check_at.isoformat() if self.last_check_at else None,
            'next_check_at': self.next_check_at.isoformat() if self.next_check_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class MonitoringSource(db.Model):
    """
    Data source configuration for a monitoring task.

    One task can have multiple sources across platforms.
    Each source tracks what to monitor and its state.
    """
    __tablename__ = 'monitoring_sources'

    # Primary key
    id = db.Column(db.Integer, primary_key=True)

    # Task relationship
    task_id = db.Column(db.Integer, db.ForeignKey('monitoring_tasks.id', ondelete='CASCADE'),
                        nullable=False, index=True)

    # Source configuration
    platform = db.Column(SQLAlchemyEnum(SourcePlatform), nullable=False)
    query_type = db.Column(SQLAlchemyEnum(SourceQueryType), nullable=False)
    query_value = db.Column(db.String(500), nullable=False)
    # e.g., platform=INSTAGRAM, query_type=USER_PROFILE, query_value="@username"
    # e.g., platform=X_TWITTER, query_type=HASHTAG, query_value="#hashtag"

    # Source-specific settings
    max_results_per_check = db.Column(db.Integer, default=20, nullable=False)
    include_media = db.Column(db.Boolean, default=True, nullable=False)

    # State tracking
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    last_result_id = db.Column(db.String(200))  # Track last seen post/tweet ID for incremental fetching
    last_check_at = db.Column(db.DateTime)
    error_count = db.Column(db.Integer, default=0, nullable=False)
    last_error = db.Column(db.Text)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    results = db.relationship('MonitoringResult', backref='source', lazy='dynamic',
                             cascade='all, delete-orphan', passive_deletes=True)

    def __repr__(self):
        return f'<MonitoringSource {self.id}: {self.platform.value} - {self.query_value}>'

    def record_error(self, error_message):
        """Record an error during source processing."""
        self.error_count += 1
        self.last_error = str(error_message)[:1000]  # Limit error length

    def clear_errors(self):
        """Clear error state after successful processing."""
        self.error_count = 0
        self.last_error = None

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'platform': self.platform.value if self.platform else None,
            'query_type': self.query_type.value if self.query_type else None,
            'query_value': self.query_value,
            'max_results_per_check': self.max_results_per_check,
            'include_media': self.include_media,
            'is_active': self.is_active,
            'last_check_at': self.last_check_at.isoformat() if self.last_check_at else None,
            'error_count': self.error_count,
            'last_error': self.last_error,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class MonitoringResult(db.Model):
    """
    Individual captured event from monitoring.

    Each post/tweet/update becomes a result with optional AI analysis.
    Results maintain forensic integrity with content hashing.
    """
    __tablename__ = 'monitoring_results'

    # Primary key
    id = db.Column(db.Integer, primary_key=True)

    # Relationships
    task_id = db.Column(db.Integer, db.ForeignKey('monitoring_tasks.id', ondelete='CASCADE'),
                        nullable=False, index=True)
    source_id = db.Column(db.Integer, db.ForeignKey('monitoring_sources.id', ondelete='CASCADE'),
                         nullable=False, index=True)

    # Result identification
    external_id = db.Column(db.String(200), nullable=False, index=True)  # Post ID, Tweet ID
    external_url = db.Column(db.String(1000))  # Direct link to the content

    # Content
    content_text = db.Column(db.Text)
    content_metadata = db.Column(db.JSON)  # Full raw data from API

    # Author information
    author_username = db.Column(db.String(200))
    author_display_name = db.Column(db.String(300))
    author_profile_url = db.Column(db.String(500))

    # Media (images/videos)
    has_media = db.Column(db.Boolean, default=False, nullable=False)
    media_count = db.Column(db.Integer, default=0, nullable=False)
    media_urls = db.Column(db.JSON)  # List of media URLs from source
    media_downloaded = db.Column(db.Boolean, default=False, nullable=False)
    media_local_paths = db.Column(db.JSON)  # Paths to downloaded files
    media_hashes = db.Column(db.JSON)  # SHA-256 hashes of downloaded media

    # Timestamps from source
    source_timestamp = db.Column(db.DateTime, index=True)  # When the post was created
    captured_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # AI Analysis
    ai_analyzed = db.Column(db.Boolean, default=False, nullable=False, index=True)
    ai_analysis_timestamp = db.Column(db.DateTime)
    ai_provider_used = db.Column(db.String(50))  # 'openai' or 'deepseek'
    ai_model_used = db.Column(db.String(100))  # Specific model version
    ai_analysis_result = db.Column(db.JSON)  # Full AI response
    ai_relevance_score = db.Column(db.Float)  # 0-1 score for objective match
    ai_summary = db.Column(db.Text)  # Human-readable summary
    ai_flags = db.Column(db.JSON)  # Specific flags/alerts raised
    ai_error = db.Column(db.Text)  # Error message if AI analysis failed

    # Alert status
    is_alert = db.Column(db.Boolean, default=False, nullable=False, index=True)  # Flagged for attention
    alert_acknowledged = db.Column(db.Boolean, default=False, nullable=False)
    alert_acknowledged_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    alert_acknowledged_at = db.Column(db.DateTime)
    alert_notes = db.Column(db.Text)

    # Evidence linkage
    saved_as_evidence = db.Column(db.Boolean, default=False, nullable=False)
    evidence_id = db.Column(db.Integer, db.ForeignKey('evidences.id'))

    # Forensic integrity
    content_hash = db.Column(db.String(64), nullable=False)  # SHA-256 of original content

    # Relationships
    acknowledged_by = db.relationship('User', foreign_keys=[alert_acknowledged_by_id])
    evidence = db.relationship('Evidence', foreign_keys=[evidence_id])

    def __repr__(self):
        return f'<MonitoringResult {self.id}: {self.external_id}>'

    @staticmethod
    def calculate_content_hash(content_text, external_id, source_timestamp):
        """Calculate SHA-256 hash for content integrity."""
        hash_input = f"{external_id}|{content_text or ''}|{source_timestamp}"
        return hashlib.sha256(hash_input.encode('utf-8')).hexdigest()

    def verify_integrity(self):
        """Verify content has not been modified."""
        expected_hash = self.calculate_content_hash(
            self.content_text,
            self.external_id,
            self.source_timestamp
        )
        return self.content_hash == expected_hash

    def acknowledge_alert(self, user_id, notes=None):
        """Acknowledge an alert."""
        self.alert_acknowledged = True
        self.alert_acknowledged_by_id = user_id
        self.alert_acknowledged_at = datetime.utcnow()
        if notes:
            self.alert_notes = notes

        # Decrement unread counter on task
        if self.task and self.task.unread_alerts_count > 0:
            self.task.unread_alerts_count -= 1

    def mark_as_alert(self, score=None, flags=None):
        """Mark this result as an alert based on AI analysis."""
        self.is_alert = True
        if score is not None:
            self.ai_relevance_score = score
        if flags:
            self.ai_flags = flags

        # Increment alert counters on task
        if self.task:
            self.task.increment_alerts()

    def to_dict(self, include_content=True, include_ai=True):
        """Convert to dictionary for API responses."""
        result = {
            'id': self.id,
            'task_id': self.task_id,
            'source_id': self.source_id,
            'external_id': self.external_id,
            'external_url': self.external_url,
            'author_username': self.author_username,
            'author_display_name': self.author_display_name,
            'has_media': self.has_media,
            'media_count': self.media_count,
            'source_timestamp': self.source_timestamp.isoformat() if self.source_timestamp else None,
            'captured_at': self.captured_at.isoformat() if self.captured_at else None,
            'is_alert': self.is_alert,
            'alert_acknowledged': self.alert_acknowledged,
            'saved_as_evidence': self.saved_as_evidence
        }

        if include_content:
            result['content_text'] = self.content_text
            result['media_urls'] = self.media_urls

        if include_ai:
            result['ai_analyzed'] = self.ai_analyzed
            result['ai_relevance_score'] = self.ai_relevance_score
            result['ai_summary'] = self.ai_summary
            result['ai_flags'] = self.ai_flags

        return result


class MonitoringCheckLog(db.Model):
    """
    Immutable log of each monitoring check execution.

    For forensic traceability and legal compliance.
    Records every monitoring execution with results.
    """
    __tablename__ = 'monitoring_check_logs'

    # Primary key
    id = db.Column(db.Integer, primary_key=True)

    # Task relationship
    task_id = db.Column(db.Integer, db.ForeignKey('monitoring_tasks.id', ondelete='CASCADE'),
                        nullable=False, index=True)

    # Execution details
    check_started_at = db.Column(db.DateTime, nullable=False, index=True)
    check_completed_at = db.Column(db.DateTime)
    duration_seconds = db.Column(db.Float)

    # Results summary
    sources_checked = db.Column(db.Integer, default=0, nullable=False)
    new_results_count = db.Column(db.Integer, default=0, nullable=False)
    ai_analyses_count = db.Column(db.Integer, default=0, nullable=False)
    alerts_generated = db.Column(db.Integer, default=0, nullable=False)
    errors_count = db.Column(db.Integer, default=0, nullable=False)

    # Status
    success = db.Column(db.Boolean, nullable=False)
    error_message = db.Column(db.Text)

    # Execution context
    triggered_by = db.Column(db.String(50), nullable=False)  # 'scheduled', 'manual'
    triggered_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    celery_task_id = db.Column(db.String(200))

    # Relationships
    triggered_by_user = db.relationship('User', foreign_keys=[triggered_by_user_id])

    def __repr__(self):
        return f'<MonitoringCheckLog {self.id}: Task {self.task_id} at {self.check_started_at}>'

    def complete(self, success=True, error_message=None):
        """Mark the check as completed."""
        self.check_completed_at = datetime.utcnow()
        self.success = success
        if error_message:
            self.error_message = str(error_message)[:2000]  # Limit length

        # Calculate duration
        if self.check_started_at:
            delta = self.check_completed_at - self.check_started_at
            self.duration_seconds = delta.total_seconds()

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'check_started_at': self.check_started_at.isoformat() if self.check_started_at else None,
            'check_completed_at': self.check_completed_at.isoformat() if self.check_completed_at else None,
            'duration_seconds': self.duration_seconds,
            'sources_checked': self.sources_checked,
            'new_results_count': self.new_results_count,
            'ai_analyses_count': self.ai_analyses_count,
            'alerts_generated': self.alerts_generated,
            'errors_count': self.errors_count,
            'success': self.success,
            'error_message': self.error_message,
            'triggered_by': self.triggered_by
        }
