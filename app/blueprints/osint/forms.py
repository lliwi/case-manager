"""
OSINT Forms
Forms for managing OSINT contacts
"""
from flask_wtf import FlaskForm
from wtforms import (
    StringField, TextAreaField, SelectField,
    SubmitField, HiddenField
)
from wtforms.validators import DataRequired, Length, Optional, ValidationError
import re


class OSINTContactForm(FlaskForm):
    """Form for creating/editing OSINT contacts"""

    contact_type = SelectField(
        'Tipo de Contacto',
        choices=[
            ('email', 'Email'),
            ('phone', 'Teléfono'),
            ('social_profile', 'Perfil Social'),
            ('username', 'Nombre de Usuario'),
            ('other', 'Otro')
        ],
        validators=[DataRequired(message='Debe seleccionar un tipo de contacto')]
    )

    contact_value = StringField(
        'Valor del Contacto',
        validators=[
            DataRequired(message='El valor del contacto es obligatorio'),
            Length(max=500, message='El valor no puede exceder 500 caracteres')
        ],
        render_kw={'placeholder': 'Ej: usuario@example.com, +34612345678, @username'}
    )

    name = StringField(
        'Nombre Asociado',
        validators=[
            Optional(),
            Length(max=200, message='El nombre no puede exceder 200 caracteres')
        ],
        render_kw={'placeholder': 'Nombre de la persona asociada (opcional)'}
    )

    description = TextAreaField(
        'Descripción / Contexto',
        validators=[Optional()],
        render_kw={
            'rows': 3,
            'placeholder': 'Contexto sobre este contacto, dónde se encontró, relevancia para el caso...'
        }
    )

    source = StringField(
        'Fuente',
        validators=[
            Optional(),
            Length(max=200, message='La fuente no puede exceder 200 caracteres')
        ],
        render_kw={'placeholder': 'Ej: Redes sociales, documento adjunto, testimonio...'}
    )

    tags = StringField(
        'Etiquetas',
        validators=[
            Optional(),
            Length(max=500, message='Las etiquetas no pueden exceder 500 caracteres')
        ],
        render_kw={'placeholder': 'Etiquetas separadas por comas (ej: sospechoso, testigo, principal)'}
    )

    case_id = SelectField(
        'Caso Asociado',
        coerce=int,
        validators=[Optional()],
        choices=[],
        render_kw={'class': 'form-select'}
    )

    submit = SubmitField('Guardar Contacto')

    def validate_contact_value(self, field):
        """Validate contact value based on contact type"""
        contact_type = self.contact_type.data
        value = field.data.strip()

        if contact_type == 'email':
            # Basic email validation
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, value):
                raise ValidationError('El formato del email no es válido')

        elif contact_type == 'phone':
            # Basic phone validation (allow international format)
            phone_pattern = r'^\+?[0-9\s\-()]{7,20}$'
            if not re.match(phone_pattern, value):
                raise ValidationError('El formato del teléfono no es válido. Use formato internacional: +34612345678')


class ValidateContactForm(FlaskForm):
    """Form for validating a contact using IPQualityScore"""

    contact_id = HiddenField('Contact ID', validators=[DataRequired()])

    notes = TextAreaField(
        'Notas (opcional)',
        validators=[Optional()],
        render_kw={
            'rows': 2,
            'placeholder': 'Notas adicionales sobre esta validación...'
        }
    )

    submit = SubmitField('Validar con IPQualityScore')


class SearchContactForm(FlaskForm):
    """Form for searching contacts"""

    search_term = StringField(
        'Buscar',
        validators=[Optional()],
        render_kw={'placeholder': 'Buscar por valor, nombre, descripción o etiquetas...'}
    )

    contact_type = SelectField(
        'Tipo',
        choices=[
            ('', 'Todos'),
            ('email', 'Email'),
            ('phone', 'Teléfono'),
            ('social_profile', 'Perfil Social'),
            ('username', 'Nombre de Usuario'),
            ('other', 'Otro')
        ],
        validators=[Optional()]
    )

    status = SelectField(
        'Estado',
        choices=[
            ('', 'Todos'),
            ('active', 'Activos'),
            ('archived', 'Archivados'),
            ('invalid', 'Inválidos')
        ],
        validators=[Optional()]
    )

    validation_status = SelectField(
        'Validación',
        choices=[
            ('', 'Todos'),
            ('validated', 'Validados'),
            ('not_validated', 'Sin Validar')
        ],
        validators=[Optional()]
    )

    case_id = SelectField(
        'Caso',
        coerce=int,
        choices=[],
        validators=[Optional()]
    )

    submit = SubmitField('Buscar')
