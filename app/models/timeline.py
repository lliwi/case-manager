"""
Timeline event model for chronological case visualization.

Per UNE 71506 forensic standards, all events must be:
- Timestamped with UTC
- Linked to evidence or observations
- Categorized for analysis
- Exportable for judicial reports
"""
from datetime import datetime
from app.extensions import db
from sqlalchemy import Enum as SQLAlchemyEnum
from enum import Enum


class EventType(Enum):
    """Timeline event type categorization."""
    # Evidence-based events
    EVIDENCE_ACQUIRED = 'Evidencia Adquirida'
    EVIDENCE_ANALYZED = 'Evidencia Analizada'

    # Observation events
    OBSERVATION = 'Observación'
    SURVEILLANCE = 'Vigilancia'
    LOCATION_SIGHTING = 'Avistamiento en Ubicación'

    # Subject activity
    SUBJECT_ACTIVITY = 'Actividad del Sujeto'
    MEETING = 'Reunión'
    COMMUNICATION = 'Comunicación'

    # Vehicle events
    VEHICLE_MOVEMENT = 'Movimiento de Vehículo'
    VEHICLE_SIGHTING = 'Avistamiento de Vehículo'

    # Digital events
    DIGITAL_ACTIVITY = 'Actividad Digital'
    SOCIAL_MEDIA_POST = 'Publicación en Redes Sociales'

    # Case milestones
    CASE_OPENED = 'Caso Abierto'
    CASE_CLOSED = 'Caso Cerrado'
    LEGITIMACY_VALIDATED = 'Legitimidad Validada'

    # Other
    NOTE = 'Nota'
    OTHER = 'Otro'


class TimelineEvent(db.Model):
    """
    Timeline event model.

    Represents a chronological event in an investigation.
    Events can be linked to evidence, locations, or be manual observations.
    """
    __tablename__ = 'timeline_events'

    # Primary key
    id = db.Column(db.Integer, primary_key=True)

    # Foreign keys
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), nullable=False)
    evidence_id = db.Column(db.Integer, db.ForeignKey('evidences.id'), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Event details
    event_type = db.Column(SQLAlchemyEnum(EventType), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    # Temporal data
    event_date = db.Column(db.DateTime, nullable=False, index=True)  # When the event actually occurred
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)  # When recorded in system
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    # Location data
    location_name = db.Column(db.String(300))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)

    # Subject/entity references
    subjects = db.Column(db.Text)  # Comma-separated subject names or IDs
    entities = db.Column(db.Text)  # Comma-separated entity references (e.g., "person:123,vehicle:456")

    # Metadata
    tags = db.Column(db.String(500))  # Comma-separated tags for filtering
    confidence_level = db.Column(db.String(20))  # 'high', 'medium', 'low', 'unconfirmed'
    source = db.Column(db.String(200))  # Source of information (witness, video, GPS, etc.)

    # Visual timeline properties
    color = db.Column(db.String(7))  # Hex color for visualization (#FF0000)
    icon = db.Column(db.String(50))  # Bootstrap icon class or emoji

    # Soft delete
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime)
    deleted_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Relationships
    case = db.relationship('Case', backref=db.backref('timeline_events', lazy='dynamic'))
    evidence = db.relationship('Evidence', backref=db.backref('timeline_events', lazy='dynamic'))
    created_by = db.relationship('User', foreign_keys=[created_by_id], backref='timeline_events_created')
    deleted_by = db.relationship('User', foreign_keys=[deleted_by_id], backref='timeline_events_deleted')

    def __repr__(self):
        return f'<TimelineEvent {self.id}: {self.title} at {self.event_date}>'

    def to_dict(self):
        """Convert event to dictionary for JSON/API responses."""
        return {
            'id': self.id,
            'case_id': self.case_id,
            'evidence_id': self.evidence_id,
            'event_type': self.event_type.value,
            'title': self.title,
            'description': self.description,
            'event_date': self.event_date.isoformat() if self.event_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'location_name': self.location_name,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'subjects': self.subjects.split(',') if self.subjects else [],
            'tags': self.tags.split(',') if self.tags else [],
            'confidence_level': self.confidence_level,
            'source': self.source,
            'color': self.color or '#3498db',  # Default blue
            'icon': self.icon or 'bi-circle-fill',
            'created_by': self.created_by.nombre if self.created_by else None
        }

    def to_vis_js(self):
        """
        Convert event to Vis.js Timeline format.

        Returns dict compatible with Vis.js Timeline library.
        """
        return {
            'id': self.id,
            'content': self.title,
            'start': self.event_date.isoformat() if self.event_date else None,
            'type': 'point',
            'title': self.description,  # Tooltip
            'className': f'event-{self.event_type.name.lower()}',
            'style': f'background-color: {self.color or "#3498db"}',
            'group': self.subjects.split(',')[0] if self.subjects else 'General'  # First subject as group
        }

    def soft_delete(self, user):
        """Soft delete the event."""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        self.deleted_by_id = user.id
        db.session.commit()

    @staticmethod
    def create_from_evidence(evidence, user, event_type=EventType.EVIDENCE_ACQUIRED):
        """
        Create timeline event automatically from evidence.

        Args:
            evidence: Evidence object
            user: User creating the event
            event_type: Type of event (default: EVIDENCE_ACQUIRED)

        Returns:
            TimelineEvent: Created event
        """
        event = TimelineEvent(
            case_id=evidence.case_id,
            evidence_id=evidence.id,
            created_by_id=user.id,
            event_type=event_type,
            title=f'Evidencia: {evidence.original_filename}',
            description=evidence.description,
            event_date=evidence.acquisition_date or evidence.uploaded_at,
            location_name=evidence.source_location,
            latitude=evidence.geolocation_lat,
            longitude=evidence.geolocation_lon,
            source=evidence.acquisition_method or 'Evidence Upload',
            color='#2ecc71',  # Green for evidence
            icon='bi-file-earmark-check'
        )

        db.session.add(event)
        db.session.commit()

        return event

    @staticmethod
    def create_case_milestone(case, user, event_type, title, description=None):
        """
        Create a timeline event for case milestones.

        Args:
            case: Case object
            user: User creating the event
            event_type: EventType (CASE_OPENED, LEGITIMACY_VALIDATED, etc.)
            title: Event title
            description: Event description (optional)

        Returns:
            TimelineEvent: Created event
        """
        event = TimelineEvent(
            case_id=case.id,
            created_by_id=user.id,
            event_type=event_type,
            title=title,
            description=description,
            event_date=datetime.utcnow(),
            color='#e74c3c',  # Red for milestones
            icon='bi-flag-fill'
        )

        db.session.add(event)
        db.session.commit()

        return event
