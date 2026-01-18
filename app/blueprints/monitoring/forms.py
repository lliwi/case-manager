"""
Monitoring forms for task and source management.
"""
from flask_wtf import FlaskForm
from wtforms import (
    StringField, TextAreaField, SelectField, IntegerField,
    BooleanField, SubmitField
)
from wtforms.fields import DateTimeLocalField
from wtforms.validators import DataRequired, Length, Optional, NumberRange, ValidationError
from app.models.monitoring import SourcePlatform, SourceQueryType, AIProvider


class MonitoringTaskForm(FlaskForm):
    """Form for creating/editing a monitoring task."""

    name = StringField(
        'Nombre de la tarea',
        validators=[
            DataRequired(message='El nombre es obligatorio'),
            Length(max=200, message='Máximo 200 caracteres')
        ],
        render_kw={'placeholder': 'Ej: Monitorización @usuario_instagram'}
    )

    description = TextAreaField(
        'Descripción',
        validators=[Optional(), Length(max=2000)],
        render_kw={
            'placeholder': 'Descripción opcional de la tarea de monitorización...',
            'rows': 3
        }
    )

    monitoring_objective = TextAreaField(
        'Objetivo de monitorización',
        validators=[
            DataRequired(message='El objetivo es obligatorio'),
            Length(min=20, max=2000, message='El objetivo debe tener entre 20 y 2000 caracteres')
        ],
        render_kw={
            'placeholder': 'Ej: Detectar actividades físicas incompatibles con una baja laboral por problemas de espalda. Buscar imágenes de deportes, ejercicio, cargar peso, etc.',
            'rows': 4
        },
        description='Describe qué quieres que la IA detecte en el contenido monitorizado'
    )

    ai_provider = SelectField(
        'Proveedor de IA',
        choices=[
            ('deepseek', 'DeepSeek (Económico - Recomendado)'),
            ('openai', 'OpenAI GPT-4 Vision (Premium)')
        ],
        default='deepseek',
        render_kw={'class': 'form-select'}
    )

    ai_analysis_enabled = BooleanField(
        'Habilitar análisis de IA',
        default=True,
        description='Si está activado, la IA analizará automáticamente el contenido capturado'
    )

    ai_prompt_template = TextAreaField(
        'Plantilla de prompt personalizado (opcional)',
        validators=[Optional(), Length(max=5000)],
        render_kw={
            'placeholder': 'Deja vacío para usar el prompt predeterminado. Usa {objective} para insertar el objetivo y {text} para el texto del post.',
            'rows': 4
        },
        description='Avanzado: Personaliza el prompt enviado a la IA'
    )

    check_interval_minutes = SelectField(
        'Intervalo de comprobación',
        choices=[
            (15, 'Cada 15 minutos'),
            (30, 'Cada 30 minutos'),
            (60, 'Cada hora'),
            (120, 'Cada 2 horas'),
            (360, 'Cada 6 horas'),
            (720, 'Cada 12 horas'),
            (1440, 'Diariamente')
        ],
        coerce=int,
        default=60,
        render_kw={'class': 'form-select'}
    )

    start_date = DateTimeLocalField(
        'Fecha de inicio',
        validators=[DataRequired(message='La fecha de inicio es obligatoria')],
        format='%Y-%m-%dT%H:%M'
    )

    end_date = DateTimeLocalField(
        'Fecha de fin (opcional)',
        validators=[Optional()],
        format='%Y-%m-%dT%H:%M',
        description='Deja vacío para monitorización indefinida'
    )

    submit = SubmitField('Guardar')

    def validate_end_date(self, field):
        """Validate that end_date is after start_date."""
        if field.data and self.start_date.data:
            if field.data <= self.start_date.data:
                raise ValidationError('La fecha de fin debe ser posterior a la fecha de inicio')


class MonitoringSourceForm(FlaskForm):
    """Form for adding/editing a monitoring source."""

    platform = SelectField(
        'Plataforma',
        choices=[
            ('X_TWITTER', 'X (Twitter)'),
            ('INSTAGRAM', 'Instagram')
        ],
        validators=[DataRequired(message='Selecciona una plataforma')],
        render_kw={'class': 'form-select'}
    )

    query_type = SelectField(
        'Tipo de consulta',
        choices=[
            ('USER_PROFILE', 'Perfil de Usuario'),
            ('HASHTAG', 'Hashtag'),
            ('SEARCH_QUERY', 'Búsqueda')
        ],
        validators=[DataRequired(message='Selecciona el tipo de consulta')],
        render_kw={'class': 'form-select'}
    )

    query_value = StringField(
        'Valor de búsqueda',
        validators=[
            DataRequired(message='El valor de búsqueda es obligatorio'),
            Length(max=500, message='Máximo 500 caracteres')
        ],
        render_kw={'placeholder': 'Ej: @usuario, #hashtag, o término de búsqueda'}
    )

    max_results_per_check = IntegerField(
        'Máximo resultados por comprobación',
        validators=[
            Optional(),
            NumberRange(min=1, max=100, message='Debe estar entre 1 y 100')
        ],
        default=20,
        render_kw={'class': 'form-control', 'min': 1, 'max': 100}
    )

    include_media = BooleanField(
        'Incluir imágenes/videos',
        default=True,
        description='Descargar y almacenar imágenes y videos para análisis'
    )

    submit = SubmitField('Añadir fuente')

    def validate_query_value(self, field):
        """Validate query value based on query type."""
        if not field.data:
            return

        query_type = self.query_type.data
        value = field.data.strip()

        if query_type == 'USER_PROFILE':
            # Remove @ if present for validation
            if value.startswith('@'):
                value = value[1:]
            if not value:
                raise ValidationError('El nombre de usuario no puede estar vacío')
            if ' ' in value:
                raise ValidationError('El nombre de usuario no puede contener espacios')

        elif query_type == 'HASHTAG':
            # Remove # if present for validation
            if value.startswith('#'):
                value = value[1:]
            if not value:
                raise ValidationError('El hashtag no puede estar vacío')
            if ' ' in value:
                raise ValidationError('El hashtag no puede contener espacios')


class AlertAcknowledgeForm(FlaskForm):
    """Form for acknowledging an alert."""

    alert_notes = TextAreaField(
        'Notas',
        validators=[Optional(), Length(max=2000)],
        render_kw={
            'placeholder': 'Añade notas sobre esta alerta...',
            'rows': 3
        }
    )

    submit = SubmitField('Reconocer alerta')


class SaveAsEvidenceForm(FlaskForm):
    """Form for saving a result as evidence."""

    description = TextAreaField(
        'Descripción de la evidencia',
        validators=[Optional(), Length(max=2000)],
        render_kw={
            'placeholder': 'Descripción opcional para la evidencia...',
            'rows': 3
        }
    )

    submit = SubmitField('Guardar como evidencia')
