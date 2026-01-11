"""
OSINT Validation Model
Stores validation results for emails and phone numbers from IPQualityScore
"""
from datetime import datetime
from app import db
from sqlalchemy.dialects.postgresql import JSON


class OSINTValidation(db.Model):
    """
    Stores OSINT validation results for contacts (emails and phones)
    Links to cases and provides caching to avoid redundant API calls
    """
    __tablename__ = 'osint_validations'

    # Primary Key
    id = db.Column(db.Integer, primary_key=True)

    # Contact Information
    contact_type = db.Column(db.Enum('email', 'phone', name='contact_type_enum'), nullable=False, index=True)
    contact_value = db.Column(db.String(200), nullable=False, index=True)

    # Validation Metadata
    validation_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    service_name = db.Column(db.String(100), nullable=False, default='ipqualityscore')
    api_key_id = db.Column(db.Integer, db.ForeignKey('api_keys.id'), nullable=True)

    # Validation Results (Key Metrics)
    is_valid = db.Column(db.Boolean, nullable=False, default=False)
    fraud_score = db.Column(db.Integer, nullable=True)  # 0-100
    risk_level = db.Column(db.String(20), nullable=True)  # low, medium, high, very_high

    # Complete API Response
    raw_data = db.Column(JSON, nullable=False)

    # Case Association (nullable = can validate without case)
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), nullable=True, index=True)

    # User who performed validation
    validated_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Notes
    notes = db.Column(db.Text, nullable=True)

    # Audit
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    case = db.relationship('Case', backref='osint_validations', lazy='joined')
    validated_by = db.relationship('User', backref='osint_validations', foreign_keys=[validated_by_id])
    api_key = db.relationship('ApiKey', backref='osint_validations')

    def __repr__(self):
        return f'<OSINTValidation {self.contact_type}:{self.contact_value} score={self.fraud_score}>'

    @classmethod
    def get_cached_validation(cls, contact_value, contact_type, max_age_days=30):
        """
        Get cached validation result if it exists and is recent enough

        Args:
            contact_value: Email or phone number
            contact_type: 'email' or 'phone'
            max_age_days: Maximum age in days to consider cache valid

        Returns:
            OSINTValidation object or None
        """
        from datetime import timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)

        return cls.query.filter(
            cls.contact_value == contact_value.lower().strip(),
            cls.contact_type == contact_type,
            cls.validation_date >= cutoff_date
        ).order_by(cls.validation_date.desc()).first()

    @classmethod
    def create_from_plugin_result(cls, contact_value, contact_type, plugin_result,
                                   user_id, case_id=None, api_key_id=None, notes=None):
        """
        Create OSINT validation record from plugin result

        Args:
            contact_value: Email or phone number
            contact_type: 'email' or 'phone'
            plugin_result: Dictionary returned by IPQualityScoreValidatorPlugin
            user_id: ID of user performing validation
            case_id: Optional case ID to link validation
            api_key_id: Optional API key ID used
            notes: Optional user notes

        Returns:
            OSINTValidation object
        """
        # Determine risk level from fraud score
        fraud_score = plugin_result.get('fraud_score', 0)
        if fraud_score >= 90:
            risk_level = 'very_high'
        elif fraud_score >= 85:
            risk_level = 'high'
        elif fraud_score >= 75:
            risk_level = 'medium'
        else:
            risk_level = 'low'

        validation = cls(
            contact_type=contact_type,
            contact_value=contact_value.lower().strip(),
            is_valid=plugin_result.get('valid', False),
            fraud_score=fraud_score,
            risk_level=risk_level,
            raw_data=plugin_result,
            case_id=case_id,
            validated_by_id=user_id,
            api_key_id=api_key_id,
            notes=notes
        )

        db.session.add(validation)
        db.session.commit()

        return validation

    def get_summary(self):
        """
        Get human-readable summary of validation

        Returns:
            Dictionary with summary information
        """
        interpretation = self.raw_data.get('interpretation', {})

        summary = {
            'contact': self.contact_value,
            'type': self.contact_type,
            'valid': self.is_valid,
            'fraud_score': self.fraud_score,
            'risk_level': self.risk_level,
            'recommendation': interpretation.get('recommendation', 'No recommendation available'),
            'validated_date': self.validation_date.strftime('%d/%m/%Y %H:%M'),
            'validated_by': self.validated_by.email if self.validated_by else 'Unknown'
        }

        # Type-specific details
        if self.contact_type == 'email':
            summary['disposable'] = self.raw_data.get('disposable', False)
            summary['smtp_score'] = self.raw_data.get('smtp_score', 0)
            summary['deliverability'] = self.raw_data.get('deliverability', 'unknown')
            summary['leaked'] = self.raw_data.get('leaked', False)
        elif self.contact_type == 'phone':
            summary['active'] = self.raw_data.get('active', False)
            summary['carrier'] = self.raw_data.get('carrier', 'Unknown')
            summary['line_type'] = self.raw_data.get('line_type', 'Unknown')
            summary['voip'] = self.raw_data.get('VOIP', False)
            summary['country'] = self.raw_data.get('country', 'Unknown')

        return summary

    def get_type_icon(self):
        """
        Get Bootstrap icon for contact type

        Returns:
            String: Bootstrap icon class
        """
        type_icons = {
            'email': 'bi-envelope',
            'phone': 'bi-telephone'
        }
        return type_icons.get(self.contact_type, 'bi-info-circle')

    def get_risk_badge_class(self):
        """
        Get Bootstrap badge class based on risk level

        Returns:
            String: Bootstrap class name
        """
        risk_classes = {
            'low': 'bg-success',
            'medium': 'bg-warning',
            'high': 'bg-warning',
            'very_high': 'bg-danger'
        }
        return risk_classes.get(self.risk_level, 'bg-secondary')

    def to_dict(self):
        """
        Convert to dictionary for API responses

        Returns:
            Dictionary representation
        """
        return {
            'id': self.id,
            'contact_type': self.contact_type,
            'contact_value': self.contact_value,
            'is_valid': self.is_valid,
            'fraud_score': self.fraud_score,
            'risk_level': self.risk_level,
            'validation_date': self.validation_date.isoformat(),
            'case_id': self.case_id,
            'validated_by': self.validated_by.email if self.validated_by else None,
            'notes': self.notes,
            'summary': self.get_summary(),
            'raw_data': self.raw_data
        }
