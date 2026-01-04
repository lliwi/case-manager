"""
Custom Relationship Types model for additional relationship categories.

Extends the base RelationshipType enum with user-defined categories.
"""
from datetime import datetime
from app.extensions import db


class RelationshipTypeCustom(db.Model):
    """
    Custom relationship types for connections not covered by base enum.

    These are additional relationship categories created by administrators
    to extend the base types in the RelationshipType enum.
    """
    __tablename__ = 'relationship_types_custom'

    id = db.Column(db.Integer, primary_key=True)

    # Type information
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)

    # Display label (how it appears in forms and graphs)
    label = db.Column(db.String(100), nullable=False)

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
    created_by = db.relationship('User', foreign_keys=[created_by_id], backref='created_relationship_types')
    deleted_by = db.relationship('User', foreign_keys=[deleted_by_id])

    def __repr__(self):
        return f'<RelationshipTypeCustom {self.name}>'

    def soft_delete(self, user):
        """Soft delete the custom type."""
        # Note: We don't check for usage in Neo4j here as it's complex
        # The admin interface should warn before deletion
        self.is_deleted = True
        self.is_active = False
        self.deleted_at = datetime.utcnow()
        self.deleted_by_id = user.id
        db.session.commit()
