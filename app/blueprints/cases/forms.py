"""
Case management forms.
"""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    StringField, TextAreaField, SelectField, DecimalField,
    DateField, BooleanField, SubmitField
)
from wtforms.validators import DataRequired, Length, Email, Optional, ValidationError
from app.models.case import LegitimacyType, CaseStatus, CasePriority
from app.services.legitimacy_service import LegitimacyService


class CaseCreateForm(FlaskForm):
    """Form for creating a new case."""

    # Client information
    cliente_nombre = StringField('Nombre del Cliente', validators=[
        DataRequired(message='El nombre del cliente es obligatorio'),
        Length(max=200)
    ])

    cliente_dni_cif = StringField('DNI/CIF/NIE del Cliente', validators=[
        DataRequired(message='El DNI/CIF del cliente es obligatorio'),
        Length(max=20)
    ])

    cliente_direccion = TextAreaField('Dirección del Cliente', validators=[
        Length(max=500)
    ])

    cliente_telefono = StringField('Teléfono del Cliente', validators=[
        Length(max=20)
    ])

    cliente_email = StringField('Email del Cliente', validators=[
        Optional(),
        Email(message='Email inválido'),
        Length(max=120)
    ])

    # Investigation subjects
    sujeto_nombres = TextAreaField('Sujeto(s) Investigado(s)', validators=[
        Optional(),
        Length(max=1000)
    ], description='Nombres de las personas a investigar (uno por línea)')

    sujeto_dni_nie = TextAreaField('DNI/NIE de Sujeto(s)', validators=[
        Optional(),
        Length(max=500)
    ], description='DNI/NIE de los investigados (uno por línea)')

    sujeto_descripcion = TextAreaField('Descripción Adicional de Sujetos', validators=[
        Optional(),
        Length(max=1000)
    ])

    # Investigation purpose
    objeto_investigacion = TextAreaField('Objeto de la Investigación', validators=[
        DataRequired(message='El objeto de la investigación es obligatorio'),
        Length(min=10, max=2000, message='Debe tener entre 10 y 2000 caracteres')
    ])

    descripcion_detallada = TextAreaField('Descripción Detallada', validators=[
        Optional(),
        Length(max=5000)
    ])

    # Legitimacy
    legitimacy_type = SelectField('Tipo de Legitimidad', validators=[
        DataRequired(message='Debe seleccionar el tipo de legitimidad')
    ], choices=[(t.name, t.value) for t in LegitimacyType])

    legitimacy_description = TextAreaField('Descripción de la Legitimidad', validators=[
        DataRequired(message='Debe describir el interés legítimo'),
        Length(min=20, max=2000)
    ])

    legitimacy_document = FileField('Documento Acreditativo', validators=[
        Optional(),
        FileAllowed(['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'],
                   'Solo se permiten archivos PDF, DOC, DOCX o imágenes')
    ])

    # Optional fields
    ubicacion_principal = StringField('Ubicación Principal', validators=[
        Optional(),
        Length(max=500)
    ])

    priority = SelectField('Prioridad', validators=[
        Optional()
    ], choices=[(p.name, p.value) for p in CasePriority])

    presupuesto_estimado = DecimalField('Presupuesto Estimado (€)', validators=[
        Optional()
    ], places=2)

    confidencial = BooleanField('Caso Confidencial', default=True)

    notas_internas = TextAreaField('Notas Internas', validators=[
        Optional(),
        Length(max=2000)
    ])

    submit = SubmitField('Crear Caso')

    def validate_cliente_dni_cif(self, field):
        """Validate Spanish DNI/CIF format."""
        result = LegitimacyService.validate_dni_cif(field.data)
        if not result['valid']:
            raise ValidationError(
                f"DNI/CIF/NIE inválido: {result.get('error', 'Formato incorrecto')}"
            )


class CaseEditForm(FlaskForm):
    """Form for editing existing case (limited fields)."""

    # Allow editing descriptive fields, not immutable libro-registro fields
    descripcion_detallada = TextAreaField('Descripción Detallada', validators=[
        Optional(),
        Length(max=5000)
    ])

    status = SelectField('Estado', validators=[
        DataRequired()
    ], choices=[(s.name, s.value) for s in CaseStatus])

    priority = SelectField('Prioridad', validators=[
        Optional()
    ], choices=[(p.name, p.value) for p in CasePriority])

    ubicacion_principal = StringField('Ubicación Principal', validators=[
        Optional(),
        Length(max=500)
    ])

    presupuesto_estimado = DecimalField('Presupuesto Estimado (€)', validators=[
        Optional()
    ], places=2)

    honorarios = DecimalField('Honorarios (€)', validators=[
        Optional()
    ], places=2)

    notas_internas = TextAreaField('Notas Internas', validators=[
        Optional(),
        Length(max=5000)
    ])

    submit = SubmitField('Actualizar Caso')


class LegitimacyValidationForm(FlaskForm):
    """Form for validating case legitimacy."""

    approved = BooleanField('Aprobar Legitimidad', default=True)

    validation_notes = TextAreaField('Notas de Validación', validators=[
        Optional(),
        Length(max=1000)
    ])

    submit = SubmitField('Validar')


class CaseCloseForm(FlaskForm):
    """Form for closing a case."""

    closure_notes = TextAreaField('Notas de Cierre', validators=[
        Optional(),
        Length(max=2000)
    ], description='Resumen de resultados y conclusiones')

    submit = SubmitField('Cerrar Caso')


class CaseSearchForm(FlaskForm):
    """Form for searching cases."""

    numero_orden = StringField('Número de Orden', validators=[Optional()])

    cliente_nombre = StringField('Nombre Cliente', validators=[Optional()])

    detective = SelectField('Detective', validators=[Optional()],
                          choices=[('', 'Todos')])  # Populated dynamically

    status = SelectField('Estado', validators=[Optional()],
                        choices=[('', 'Todos')] + [(s.name, s.value) for s in CaseStatus])

    legitimacy_type = SelectField('Tipo de Legitimidad', validators=[Optional()],
                                 choices=[('', 'Todos')] + [(t.name, t.value) for t in LegitimacyType])

    fecha_desde = DateField('Fecha Desde', validators=[Optional()],
                           format='%Y-%m-%d')

    fecha_hasta = DateField('Fecha Hasta', validators=[Optional()],
                           format='%Y-%m-%d')

    submit = SubmitField('Buscar')
