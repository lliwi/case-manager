"""
Forms for admin functionality.
"""
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, BooleanField, SelectMultipleField
from wtforms.validators import DataRequired, Length, Optional


class LegitimacyTypeCustomForm(FlaskForm):
    """Form for creating/editing custom legitimacy types."""
    name = StringField(
        'Nombre del Tipo',
        validators=[
            DataRequired(message='El nombre es obligatorio'),
            Length(min=3, max=100, message='El nombre debe tener entre 3 y 100 caracteres')
        ],
        render_kw={'placeholder': 'Ej: Investigación de Propiedad Intelectual'}
    )

    description = TextAreaField(
        'Descripción',
        validators=[
            DataRequired(message='La descripción es obligatoria'),
            Length(min=10, message='La descripción debe tener al menos 10 caracteres')
        ],
        render_kw={
            'placeholder': 'Descripción detallada del tipo de investigación y sus requisitos legales...',
            'rows': 5
        }
    )

    legal_reference = StringField(
        'Referencia Legal (opcional)',
        validators=[Optional(), Length(max=500)],
        render_kw={'placeholder': 'Ej: Art. 48 Ley 5/2014, RGPD Art. 6.1.f'}
    )

    is_active = BooleanField(
        'Activo',
        default=True
    )
