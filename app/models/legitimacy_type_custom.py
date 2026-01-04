"""
Custom Legitimacy Types model for additional investigation types.

Extends the base LegitimacyType enum with user-defined categories.
"""
from datetime import datetime
from app.extensions import db


class LegitimacyTypeCustom(db.Model):
    """
    Custom legitimacy types for investigations not covered by base enum.

    These are additional investigation categories created by administrators
    to extend the legally-defined base types in the LegitimacyType enum.
    """
    __tablename__ = 'legitimacy_types_custom'

    id = db.Column(db.Integer, primary_key=True)

    # Type information
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)

    # Legal reference (optional)
    legal_reference = db.Column(db.String(500))

    # Administrative
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Soft delete (for audit trail preservation)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime)
    deleted_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Relationships
    created_by = db.relationship('User', foreign_keys=[created_by_id], backref='created_legitimacy_types')
    deleted_by = db.relationship('User', foreign_keys=[deleted_by_id])

    def __repr__(self):
        return f'<LegitimacyTypeCustom {self.name}>'

    @property
    def case_count(self):
        """Get count of cases using this custom type."""
        from app.models.case import Case
        return Case.query.filter(
            Case.legitimacy_type_custom_id == self.id,
            Case.is_deleted == False
        ).count()

    def soft_delete(self, user):
        """Soft delete the custom type."""
        if self.case_count > 0:
            raise ValueError(
                f"Cannot delete legitimacy type '{self.name}' - "
                f"it is currently used by {self.case_count} case(s)"
            )

        self.is_deleted = True
        self.is_active = False
        self.deleted_at = datetime.utcnow()
        self.deleted_by_id = user.id
        db.session.commit()
