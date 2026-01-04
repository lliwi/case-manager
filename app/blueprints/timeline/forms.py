"""
Timeline forms.
"""
from flask_wtf import FlaskForm
from wtforms import (
    StringField, TextAreaField, SelectField, DateTimeLocalField,
    FloatField, HiddenField, SubmitField
)
from wtforms.validators import DataRequired, Length, Optional, NumberRange
from app.models.timeline import EventType


class TimelineEventForm(FlaskForm):
    """Form for creating/editing timeline events."""

    event_type = SelectField(
        'Tipo de Evento',
        validators=[DataRequired(message='Seleccione el tipo de evento')],
        choices=[(t.name, t.value) for t in EventType]
    )

    title = StringField(
        'Título del Evento',
        validators=[
            DataRequired(message='El título es obligatorio'),
            Length(max=200)
        ]
    )

    description = TextAreaField(
        'Descripción',
        validators=[Length(max=5000)]
    )

    event_date = DateTimeLocalField(
        'Fecha y Hora del Evento',
        format='%Y-%m-%dT%H:%M',
        validators=[DataRequired(message='La fecha del evento es obligatoria')]
    )

    location_name = StringField(
        'Ubicación',
        validators=[Length(max=300)]
    )

    latitude = FloatField(
        'Latitud',
        validators=[Optional(), NumberRange(min=-90, max=90)]
    )

    longitude = FloatField(
        'Longitud',
        validators=[Optional(), NumberRange(min=-180, max=180)]
    )

    subjects = StringField(
        'Sujetos Involucrados',
        validators=[Length(max=500)],
        description='Nombres separados por comas'
    )

    tags = StringField(
        'Etiquetas',
        validators=[Length(max=500)],
        description='Etiquetas separadas por comas para filtrado'
    )

    confidence_level = SelectField(
        'Nivel de Confianza',
        choices=[
            ('high', 'Alto'),
            ('medium', 'Medio'),
            ('low', 'Bajo'),
            ('unconfirmed', 'No Confirmado')
        ],
        default='medium'
    )

    source = StringField(
        'Fuente de Información',
        validators=[Length(max=200)],
        description='Testigo, vídeo, GPS, documentación, etc.'
    )

    color = StringField(
        'Color (Hex)',
        validators=[Length(max=7)],
        description='Color para visualización (ej: #FF5733)'
    )

    evidence_id = HiddenField('Evidence ID')

    submit = SubmitField('Guardar Evento')


class TimelineFilterForm(FlaskForm):
    """Form for filtering timeline events."""

    date_from = DateTimeLocalField(
        'Desde',
        format='%Y-%m-%dT%H:%M',
        validators=[Optional()]
    )

    date_to = DateTimeLocalField(
        'Hasta',
        format='%Y-%m-%dT%H:%M',
        validators=[Optional()]
    )

    event_types = SelectField(
        'Tipo de Evento',
        choices=[('', 'Todos')] + [(t.name, t.value) for t in EventType],
        default=''
    )

    subjects = StringField(
        'Sujeto',
        validators=[Length(max=200)]
    )

    tags = StringField(
        'Etiquetas',
        validators=[Length(max=500)]
    )

    confidence_level = SelectField(
        'Nivel de Confianza',
        choices=[
            ('', 'Todos'),
            ('high', 'Alto'),
            ('medium', 'Medio'),
            ('low', 'Bajo'),
            ('unconfirmed', 'No Confirmado')
        ],
        default=''
    )

    has_evidence = SelectField(
        'Con Evidencia',
        choices=[
            ('', 'Todos'),
            ('yes', 'Sí'),
            ('no', 'No')
        ],
        default=''
    )

    submit = SubmitField('Filtrar')
