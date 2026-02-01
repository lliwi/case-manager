"""
Report model for generating forensic investigation reports.

Complies with Spanish legal requirements for investigative reports.
"""
from app.extensions import db
from datetime import datetime
from enum import Enum


class ReportType(Enum):
    """Types of investigative reports."""
    INFORME_FINAL = "Informe Final"
    INFORME_PARCIAL = "Informe Parcial"
    INFORME_PRELIMINAR = "Informe Preliminar"
    DICTAMEN_PERICIAL = "Dictamen Pericial"
    ANEXO_TECNICO = "Anexo Técnico"


class ReportStatus(Enum):
    """Report generation status."""
    DRAFT = "Borrador"
    GENERATING = "Generando"
    COMPLETED = "Completado"
    FAILED = "Fallido"
    SIGNED = "Firmado"


class Report(db.Model):
    """Model for investigation reports."""

    __tablename__ = 'reports'

    # Primary key
    id = db.Column(db.Integer, primary_key=True)

    # Foreign keys
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Report metadata
    report_type = db.Column(db.Enum(ReportType), nullable=False, default=ReportType.INFORME_FINAL)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)

    # Report content
    introduction = db.Column(db.Text)
    methodology = db.Column(db.Text)
    findings = db.Column(db.Text)
    conclusions = db.Column(db.Text)
    recommendations = db.Column(db.Text)

    # Technical details
    include_evidence_list = db.Column(db.Boolean, default=True)
    include_timeline = db.Column(db.Boolean, default=True)
    include_graph = db.Column(db.Boolean, default=False)
    include_chain_of_custody = db.Column(db.Boolean, default=True)
    include_plugin_results = db.Column(db.Boolean, default=False)
    include_evidence_thumbnails = db.Column(db.Boolean, default=False)
    include_osint_contacts = db.Column(db.Boolean, default=False)

    # PDF file information
    file_path = db.Column(db.String(500))  # Path to generated PDF
    file_size = db.Column(db.Integer)  # File size in bytes
    file_hash_sha256 = db.Column(db.String(64))  # SHA-256 hash of PDF
    file_hash_sha512 = db.Column(db.String(128))  # SHA-512 hash of PDF

    # DOCX file information
    docx_file_path = db.Column(db.String(500))
    docx_file_size = db.Column(db.Integer)
    docx_file_hash_sha256 = db.Column(db.String(64))
    docx_file_hash_sha512 = db.Column(db.String(128))

    # Digital signature
    is_signed = db.Column(db.Boolean, default=False)
    signature_data = db.Column(db.Text)  # Digital signature blob
    signature_timestamp = db.Column(db.DateTime)
    signer_name = db.Column(db.String(200))
    signer_tip = db.Column(db.String(50))

    # Status and timestamps
    status = db.Column(db.Enum(ReportStatus), nullable=False, default=ReportStatus.DRAFT)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    generated_at = db.Column(db.DateTime)  # When PDF was generated
    signed_at = db.Column(db.DateTime)  # When report was signed

    # Version control
    version = db.Column(db.Integer, default=1)
    parent_report_id = db.Column(db.Integer, db.ForeignKey('reports.id'), nullable=True)

    # Soft delete
    is_deleted = db.Column(db.Boolean, default=False)
    deleted_at = db.Column(db.DateTime)

    # Additional metadata (JSON)
    extra_data = db.Column(db.JSON)

    # Relationships
    case = db.relationship('Case', backref=db.backref('reports', lazy='dynamic'))
    created_by = db.relationship('User', backref=db.backref('created_reports', lazy='dynamic'))
    children = db.relationship('Report', backref=db.backref('parent', remote_side=[id]))

    def __repr__(self):
        return f'<Report {self.id}: {self.title}>'

    def to_dict(self):
        """Convert report to dictionary."""
        return {
            'id': self.id,
            'case_id': self.case_id,
            'case_numero_orden': self.case.numero_orden if self.case else None,
            'report_type': self.report_type.value if self.report_type else None,
            'title': self.title,
            'description': self.description,
            'status': self.status.value if self.status else None,
            'is_signed': self.is_signed,
            'version': self.version,
            'file_hash_sha256': self.file_hash_sha256,
            'created_by': self.created_by.nombre if self.created_by else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'generated_at': self.generated_at.isoformat() if self.generated_at else None,
            'signed_at': self.signed_at.isoformat() if self.signed_at else None
        }

    def get_full_title(self):
        """Get full report title with case reference."""
        return f"{self.report_type.value} - Caso {self.case.numero_orden}: {self.title}"

    def get_file_name(self):
        """Get standardized file name for the PDF report."""
        case_number = self.case.numero_orden.replace('/', '-')
        timestamp = self.created_at.strftime('%Y%m%d')
        return f"Informe_{case_number}_{timestamp}_v{self.version}.pdf"

    def get_docx_file_name(self):
        """Get standardized file name for the DOCX report."""
        case_number = self.case.numero_orden.replace('/', '-')
        timestamp = self.created_at.strftime('%Y%m%d')
        return f"Informe_{case_number}_{timestamp}_v{self.version}.docx"

    def mark_as_generated(self, file_path, file_size, sha256_hash, sha512_hash):
        """
        Mark report as successfully generated.

        Args:
            file_path: Path to the generated PDF file
            file_size: Size of the file in bytes
            sha256_hash: SHA-256 hash of the file
            sha512_hash: SHA-512 hash of the file
        """
        self.file_path = file_path
        self.file_size = file_size
        self.file_hash_sha256 = sha256_hash
        self.file_hash_sha512 = sha512_hash
        self.status = ReportStatus.COMPLETED
        self.generated_at = datetime.utcnow()
        db.session.commit()

    def mark_docx_as_generated(self, file_path, file_size, sha256_hash, sha512_hash):
        """Mark DOCX as successfully generated."""
        self.docx_file_path = file_path
        self.docx_file_size = file_size
        self.docx_file_hash_sha256 = sha256_hash
        self.docx_file_hash_sha512 = sha512_hash
        if self.status in (ReportStatus.DRAFT, ReportStatus.GENERATING):
            self.status = ReportStatus.COMPLETED
        self.generated_at = self.generated_at or datetime.utcnow()
        db.session.commit()

    def mark_as_signed(self, signature_data, signer_name, signer_tip):
        """
        Mark report as digitally signed.

        Args:
            signature_data: Digital signature blob
            signer_name: Name of the person who signed
            signer_tip: TIP number of the signer
        """
        self.is_signed = True
        self.signature_data = signature_data
        self.signer_name = signer_name
        self.signer_tip = signer_tip
        self.signature_timestamp = datetime.utcnow()
        self.signed_at = datetime.utcnow()
        self.status = ReportStatus.SIGNED
        db.session.commit()

    def create_new_version(self):
        """
        Create a new version of this report.

        Returns:
            Report: New report instance
        """
        new_report = Report(
            case_id=self.case_id,
            created_by_id=self.created_by_id,
            report_type=self.report_type,
            title=self.title,
            description=self.description,
            introduction=self.introduction,
            methodology=self.methodology,
            findings=self.findings,
            conclusions=self.conclusions,
            recommendations=self.recommendations,
            include_evidence_list=self.include_evidence_list,
            include_timeline=self.include_timeline,
            include_graph=self.include_graph,
            include_chain_of_custody=self.include_chain_of_custody,
            include_plugin_results=self.include_plugin_results,
            include_evidence_thumbnails=self.include_evidence_thumbnails,
            include_osint_contacts=self.include_osint_contacts,
            version=self.version + 1,
            parent_report_id=self.id,
            status=ReportStatus.DRAFT
        )
        db.session.add(new_report)
        db.session.commit()
        return new_report

    @staticmethod
    def get_latest_version(case_id, report_type):
        """
        Get the latest version of a report for a case.

        Args:
            case_id: Case ID
            report_type: ReportType enum

        Returns:
            Report or None
        """
        return Report.query.filter_by(
            case_id=case_id,
            report_type=report_type,
            is_deleted=False
        ).order_by(Report.version.desc()).first()
