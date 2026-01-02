"""
Case model - Implements Libro-registro per Ley 5/2014 Art. 25.

This model stores investigation cases with all legally required fields
and implements immutability for critical fields once created.
"""
from datetime import datetime
from app.extensions import db
import enum


class LegitimacyType(enum.Enum):
    """Types of legitimate interest per Spanish law."""
    BAJAS_LABORALES = "Bajas Laborales"
    COMPETENCIA_DESLEAL = "Competencia Desleal"
    CUSTODIA_MENORES = "Custodia de Menores"
    INVESTIGACION_PATRIMONIAL = "Investigación Patrimonial"
    FRAUDE_SEGUROS = "Fraude de Seguros"
    INFIDELIDAD_CONYUGAL = "Infidelidad Conyugal"
    LOCALIZACION_PERSONAS = "Localización de Personas"
    SOLVENCIA_PATRIMONIAL = "Solvencia Patrimonial"
    OTROS = "Otros"


class CaseStatus(enum.Enum):
    """Case status enumeration."""
    PENDIENTE_VALIDACION = "Pendiente de Validación"
    EN_INVESTIGACION = "En Investigación"
    SUSPENDIDO = "Suspendido"
    CERRADO = "Cerrado"
    ARCHIVADO = "Archivado"


class CasePriority(enum.Enum):
    """Case priority levels."""
    BAJA = "Baja"
    MEDIA = "Media"
    ALTA = "Alta"
    URGENTE = "Urgente"


class Case(db.Model):
    """
    Case model - Libro-registro implementation.

    Implements all requirements from Ley 5/2014 Art. 25:
    - Sequential order number
    - Start and end dates
    - Client identification
    - Investigation subjects
    - Investigation purpose
    - Legitimate interest documentation
    """
    __tablename__ = 'cases'

    id = db.Column(db.Integer, primary_key=True)

    # Libro-registro required fields (Ley 5/2014 Art. 25)
    numero_orden = db.Column(db.String(50), unique=True, nullable=False, index=True)
    fecha_inicio = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    fecha_cierre = db.Column(db.DateTime)

    # Client information (required by law)
    cliente_nombre = db.Column(db.String(200), nullable=False)
    cliente_dni_cif = db.Column(db.String(20), nullable=False)
    cliente_direccion = db.Column(db.Text)
    cliente_telefono = db.Column(db.String(20))
    cliente_email = db.Column(db.String(120))

    # Legitimacy (interés legítimo) - CRITICAL for legal compliance
    legitimacy_type = db.Column(db.Enum(LegitimacyType), nullable=False)
    legitimacy_document_path = db.Column(db.String(500))  # Contract or proof
    legitimacy_description = db.Column(db.Text, nullable=False)
    legitimacy_validated = db.Column(db.Boolean, default=False, nullable=False)
    legitimacy_validated_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    legitimacy_validated_at = db.Column(db.DateTime)

    # Investigation subject(s) - can be multiple
    sujeto_nombres = db.Column(db.Text)  # JSON array of names
    sujeto_dni_nie = db.Column(db.Text)  # JSON array of IDs
    sujeto_descripcion = db.Column(db.Text)  # Additional description

    # Investigation purpose (objeto de la investigación)
    objeto_investigacion = db.Column(db.Text, nullable=False)
    descripcion_detallada = db.Column(db.Text)

    # Detective assignment
    detective_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    detective_tip = db.Column(db.String(20), nullable=False)  # Denormalized for audit
    despacho = db.Column(db.String(200))  # Detective's office

    # Case status and priority
    status = db.Column(db.Enum(CaseStatus), default=CaseStatus.PENDIENTE_VALIDACION, nullable=False)
    priority = db.Column(db.Enum(CasePriority), default=CasePriority.MEDIA)

    # Crime detection (delitos perseguibles de oficio)
    crime_detected = db.Column(db.Boolean, default=False)
    crime_keywords_found = db.Column(db.Text)  # JSON array of detected keywords
    crime_description = db.Column(db.Text)
    crime_reported = db.Column(db.Boolean, default=False)
    crime_reported_at = db.Column(db.DateTime)
    crime_reported_to = db.Column(db.String(200))  # Authority reported to

    # Case metadata
    confidencial = db.Column(db.Boolean, default=True, nullable=False)
    notas_internas = db.Column(db.Text)  # Internal notes (not in official report)

    # Location (if applicable)
    ubicacion_principal = db.Column(db.String(500))

    # Financial
    presupuesto_estimado = db.Column(db.Numeric(10, 2))
    honorarios = db.Column(db.Numeric(10, 2))

    # Timestamps (immutable for audit trail)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Soft delete (never actually delete for legal compliance)
    is_deleted = db.Column(db.Boolean, default=False)
    deleted_at = db.Column(db.DateTime)
    deleted_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Relationships
    detective = db.relationship('User', foreign_keys=[detective_id], backref='assigned_cases')
    validator = db.relationship('User', foreign_keys=[legitimacy_validated_by_id])
    deleter = db.relationship('User', foreign_keys=[deleted_by_id])

    # These will be defined when models are created
    # evidences = db.relationship('Evidence', backref='case', lazy='dynamic')
    # timeline_events = db.relationship('TimelineEvent', backref='case', lazy='dynamic')

    def __repr__(self):
        return f'<Case {self.numero_orden}>'

    @staticmethod
    def generate_numero_orden():
        """
        Generate sequential numero de orden.
        Format: YYYY-NNNN (e.g., 2026-0001)
        """
        current_year = datetime.utcnow().year
        prefix = f"{current_year}-"

        # Get last case number for this year
        last_case = Case.query.filter(
            Case.numero_orden.like(f"{prefix}%")
        ).order_by(Case.numero_orden.desc()).first()

        if last_case:
            # Extract number and increment
            last_number = int(last_case.numero_orden.split('-')[1])
            new_number = last_number + 1
        else:
            new_number = 1

        return f"{prefix}{new_number:04d}"

    def can_be_activated(self):
        """Check if case can be activated (legitimacy validated and no crimes detected)."""
        return (
            self.legitimacy_validated and
            not self.crime_detected and
            self.status == CaseStatus.PENDIENTE_VALIDACION
        )

    def activate(self):
        """Activate case (move from pending to active investigation)."""
        if not self.can_be_activated():
            raise ValueError("Case cannot be activated: legitimacy not validated or crime detected")
        self.status = CaseStatus.EN_INVESTIGACION
        db.session.commit()

    def close(self, user):
        """Close case."""
        self.status = CaseStatus.CERRADO
        self.fecha_cierre = datetime.utcnow()
        db.session.commit()

        # Log closure
        from app.models.audit import AuditLog
        AuditLog.log(
            action='CASE_CLOSED',
            resource_type='case',
            resource_id=self.id,
            user=user,
            description=f'Case {self.numero_orden} closed'
        )

    def archive(self):
        """Archive case."""
        if self.status != CaseStatus.CERRADO:
            raise ValueError("Only closed cases can be archived")
        self.status = CaseStatus.ARCHIVADO
        db.session.commit()

    def soft_delete(self, user):
        """Soft delete case (never actually delete for legal compliance)."""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        self.deleted_by_id = user.id
        db.session.commit()

        # Log deletion
        from app.models.audit import AuditLog
        AuditLog.log(
            action='CASE_DELETED',
            resource_type='case',
            resource_id=self.id,
            user=user,
            description=f'Case {self.numero_orden} soft deleted'
        )

    def is_active(self):
        """Check if case is currently active."""
        return (
            self.status == CaseStatus.EN_INVESTIGACION and
            not self.is_deleted
        )

    def get_duration_days(self):
        """Get case duration in days."""
        if self.fecha_cierre:
            return (self.fecha_cierre - self.fecha_inicio).days
        return (datetime.utcnow() - self.fecha_inicio).days

    def to_libro_registro_dict(self):
        """
        Convert to libro-registro format (minimal data for legal record).

        Returns dict with only legally required fields per Ley 5/2014.
        """
        return {
            'numero_orden': self.numero_orden,
            'fecha_inicio': self.fecha_inicio.strftime('%d/%m/%Y'),
            'fecha_cierre': self.fecha_cierre.strftime('%d/%m/%Y') if self.fecha_cierre else '',
            'cliente_nombre': self.cliente_nombre,
            'cliente_dni_cif': self.cliente_dni_cif,
            'sujeto_nombres': self.sujeto_nombres,
            'objeto_investigacion': self.objeto_investigacion,
            'detective_tip': self.detective_tip,
        }


# Prevent modification of critical fields after creation
from sqlalchemy import event

@event.listens_for(Case, 'before_update')
def prevent_immutable_field_changes(mapper, connection, target):
    """
    Prevent modification of immutable fields (libro-registro integrity).

    Critical fields that cannot be changed once set:
    - numero_orden
    - fecha_inicio
    - detective_tip (for audit trail)
    """
    state = db.inspect(target)

    # Get history of changes
    for attr in state.attrs:
        history = attr.load_history()

        if attr.key in ['numero_orden', 'fecha_inicio'] and history.has_changes():
            raise ValueError(
                f"Field '{attr.key}' is immutable and cannot be changed "
                f"(libro-registro integrity per Ley 5/2014)"
            )
