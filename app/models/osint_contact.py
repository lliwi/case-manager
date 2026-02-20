"""
OSINT Contact Model
Manages contacts under investigation (emails, phones, social profiles, etc.)
"""
from datetime import datetime
from app import db
from sqlalchemy.dialects.postgresql import JSON


class OSINTContact(db.Model):
    """
    Represents a contact under investigation
    Can be email, phone, social profile, username, etc.
    """
    __tablename__ = 'osint_contacts'

    # Primary Key
    id = db.Column(db.Integer, primary_key=True)

    # Contact Information
    contact_type = db.Column(db.String(50), nullable=False, index=True)
    contact_value = db.Column(db.String(500), nullable=False, index=True)

    # Additional Information
    name = db.Column(db.String(200), nullable=True)  # Associated person name if known
    description = db.Column(db.Text, nullable=True)  # Context about this contact
    source = db.Column(db.String(200), nullable=True)  # Where was this contact found

    # Validation Status
    is_validated = db.Column(db.Boolean, default=False, index=True)
    validation_date = db.Column(db.DateTime, nullable=True)
    validation_result_id = db.Column(db.Integer, db.ForeignKey('osint_validations.id'), nullable=True)

    # Risk Assessment (from validation)
    fraud_score = db.Column(db.Integer, nullable=True)  # 0-100
    risk_level = db.Column(db.String(20), nullable=True)  # low, medium, high, very_high

    # Case Association
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), nullable=True, index=True)

    # Additional metadata
    extra_data = db.Column(JSON, nullable=True)  # Flexible field for extra data

    # Tags for organization
    tags = db.Column(db.String(500), nullable=True)  # Comma-separated tags

    # Status
    status = db.Column(
        db.Enum('active', 'archived', 'invalid', name='osint_contact_status_enum'),
        default='active',
        nullable=False,
        index=True
    )

    # Audit fields
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Soft delete
    is_deleted = db.Column(db.Boolean, default=False, nullable=False, index=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    deleted_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Relationships
    case = db.relationship('Case', backref='osint_contacts', lazy='joined')
    created_by = db.relationship('User', foreign_keys=[created_by_id], backref='created_osint_contacts')
    deleted_by = db.relationship('User', foreign_keys=[deleted_by_id], backref='deleted_osint_contacts')
    validation_result = db.relationship('OSINTValidation', foreign_keys=[validation_result_id],
                                       backref='contact', uselist=False)

    def __repr__(self):
        return f'<OSINTContact {self.contact_type}:{self.contact_value}>'

    @classmethod
    def create(cls, contact_type, contact_value, created_by_id, name=None,
               description=None, source=None, case_id=None, tags=None, extra_data=None):
        """
        Create a new OSINT contact

        Args:
            contact_type: Type of contact (email, phone, etc.)
            contact_value: The actual contact value
            created_by_id: User ID who created this contact
            name: Optional associated person name
            description: Optional description/context
            source: Optional source where contact was found
            case_id: Optional case ID to link
            tags: Optional comma-separated tags
            extra_data: Optional additional metadata as dict

        Returns:
            OSINTContact object
        """
        contact = cls(
            contact_type=contact_type,
            contact_value=contact_value.strip(),
            name=name,
            description=description,
            source=source,
            case_id=case_id,
            tags=tags,
            extra_data=extra_data,
            created_by_id=created_by_id
        )

        db.session.add(contact)
        db.session.commit()

        return contact

    def update_from_validation(self, validation_result):
        """
        Update contact with validation results

        Args:
            validation_result: OSINTValidation object
        """
        self.is_validated = True
        self.validation_date = validation_result.validation_date
        self.validation_result_id = validation_result.id
        self.fraud_score = validation_result.fraud_score
        self.risk_level = validation_result.risk_level

        # Update status based on validation
        if not validation_result.is_valid:
            self.status = 'invalid'

        db.session.commit()

    def soft_delete(self, user_id):
        """
        Soft delete this contact

        Args:
            user_id: ID of user performing deletion
        """
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        self.deleted_by_id = user_id
        db.session.commit()

    def get_tags_list(self):
        """
        Get tags as a list

        Returns:
            List of tag strings
        """
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(',') if tag.strip()]

    def get_risk_badge_class(self):
        """
        Get Bootstrap badge class based on risk level

        Returns:
            String: Bootstrap class name
        """
        if not self.is_validated:
            return 'bg-secondary'

        risk_classes = {
            'low': 'bg-success',
            'medium': 'bg-warning',
            'high': 'bg-warning',
            'very_high': 'bg-danger'
        }
        return risk_classes.get(self.risk_level, 'bg-secondary')

    def get_status_badge_class(self):
        """
        Get Bootstrap badge class based on status

        Returns:
            String: Bootstrap class name
        """
        status_classes = {
            'active': 'bg-primary',
            'archived': 'bg-secondary',
            'invalid': 'bg-danger'
        }
        return status_classes.get(self.status, 'bg-secondary')

    def get_type_icon(self):
        """
        Get Bootstrap icon for contact type

        Returns:
            String: Bootstrap icon class
        """
        type_icons = {
            'email': 'bi-envelope',
            'phone': 'bi-telephone',
            'social_profile': 'bi-person-circle',
            'username': 'bi-person-badge',
            'other': 'bi-info-circle'
        }
        return type_icons.get(self.contact_type, 'bi-info-circle')

    def to_dict(self, include_validation=False):
        """
        Convert to dictionary for API responses

        Args:
            include_validation: Include full validation result

        Returns:
            Dictionary representation
        """
        data = {
            'id': self.id,
            'contact_type': self.contact_type,
            'contact_value': self.contact_value,
            'name': self.name,
            'description': self.description,
            'source': self.source,
            'is_validated': self.is_validated,
            'validation_date': self.validation_date.isoformat() if self.validation_date else None,
            'fraud_score': self.fraud_score,
            'risk_level': self.risk_level,
            'case_id': self.case_id,
            'tags': self.get_tags_list(),
            'status': self.status,
            'created_by': self.created_by.email if self.created_by else None,
            'created_at': self.created_at.isoformat(),
            'extra_data': self.extra_data
        }

        if include_validation and self.validation_result:
            data['validation_result'] = self.validation_result.to_dict()

        return data

    @classmethod
    def get_active_contacts(cls, case_id=None, contact_type=None):
        """
        Get active (non-deleted) contacts with optional filters

        Args:
            case_id: Optional case ID filter
            contact_type: Optional contact type filter

        Returns:
            Query object
        """
        query = cls.query.filter_by(is_deleted=False)

        if case_id:
            query = query.filter_by(case_id=case_id)

        if contact_type:
            query = query.filter_by(contact_type=contact_type)

        return query.order_by(cls.created_at.desc())

    @classmethod
    def search(cls, search_term, case_id=None):
        """
        Search contacts by value, name, or description

        Args:
            search_term: Search term
            case_id: Optional case ID filter

        Returns:
            Query object
        """
        search_pattern = f'%{search_term}%'
        query = cls.query.filter(
            cls.is_deleted == False,
            db.or_(
                cls.contact_value.ilike(search_pattern),
                cls.name.ilike(search_pattern),
                cls.description.ilike(search_pattern),
                cls.tags.ilike(search_pattern)
            )
        )

        if case_id:
            query = query.filter_by(case_id=case_id)

        return query.order_by(cls.created_at.desc())
