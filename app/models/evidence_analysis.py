"""
Evidence Analysis Model

Stores results from forensic plugin analyses performed on evidence files.
Provides forensic traceability and audit trail for all analytical operations.
"""
from datetime import datetime
from app.extensions import db
from sqlalchemy.dialects.postgresql import JSONB


class EvidenceAnalysis(db.Model):
    """
    Forensic analysis results for evidence files.

    Each record represents one execution of a forensic plugin on an evidence file,
    storing the complete analysis results with timestamp and analyst identification.
    """
    __tablename__ = 'evidence_analyses'

    id = db.Column(db.Integer, primary_key=True)

    # Evidence and Plugin Info
    evidence_id = db.Column(
        db.Integer,
        db.ForeignKey('evidences.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    plugin_name = db.Column(db.String(100), nullable=False)
    plugin_version = db.Column(db.String(20), nullable=True)

    # Analysis Results
    success = db.Column(db.Boolean, nullable=False, default=False)
    result_data = db.Column(JSONB, nullable=False)
    error_message = db.Column(db.Text, nullable=True)

    # Audit Fields
    analyzed_by_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id'),
        nullable=False
    )
    analyzed_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True
    )

    # Relationships
    evidence = db.relationship(
        'Evidence',
        backref=db.backref('analyses', lazy='dynamic', cascade='all, delete-orphan')
    )
    analyzed_by = db.relationship('User', backref='forensic_analyses')

    def __repr__(self):
        return f'<EvidenceAnalysis {self.id}: {self.plugin_name} on Evidence {self.evidence_id}>'

    def to_dict(self):
        """Convert analysis to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'evidence_id': self.evidence_id,
            'plugin_name': self.plugin_name,
            'plugin_version': self.plugin_version,
            'success': self.success,
            'result_data': self.result_data,
            'error_message': self.error_message,
            'analyzed_by': {
                'id': self.analyzed_by.id,
                'nombre': self.analyzed_by.nombre,
                'tip_number': self.analyzed_by.tip_number
            },
            'analyzed_at': self.analyzed_at.isoformat() if self.analyzed_at else None
        }

    @staticmethod
    def get_latest_by_plugin(evidence_id, plugin_name):
        """Get the most recent analysis for a specific evidence and plugin."""
        return EvidenceAnalysis.query.filter_by(
            evidence_id=evidence_id,
            plugin_name=plugin_name
        ).order_by(EvidenceAnalysis.analyzed_at.desc()).first()

    @staticmethod
    def get_all_for_evidence(evidence_id):
        """Get all analyses for a specific evidence, ordered by date."""
        return EvidenceAnalysis.query.filter_by(
            evidence_id=evidence_id
        ).order_by(EvidenceAnalysis.analyzed_at.desc()).all()
