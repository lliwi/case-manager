"""
Forms for admin functionality.
"""
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, BooleanField, SelectMultipleField, SelectField, PasswordField, IntegerField
from wtforms.validators import DataRequired, Length, Optional, NumberRange, Regexp


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


class RelationshipTypeCustomForm(FlaskForm):
    """Form for creating/editing custom relationship types."""
    name = StringField(
        'Nombre del Tipo (ID interno)',
        validators=[
            DataRequired(message='El nombre es obligatorio'),
            Length(min=3, max=100, message='El nombre debe tener entre 3 y 100 caracteres')
        ],
        render_kw={'placeholder': 'Ej: COMPARTE_CUENTA_CON'}
    )

    label = StringField(
        'Etiqueta (texto visible)',
        validators=[
            DataRequired(message='La etiqueta es obligatoria'),
            Length(min=3, max=100, message='La etiqueta debe tener entre 3 y 100 caracteres')
        ],
        render_kw={'placeholder': 'Ej: Comparte cuenta con'}
    )

    description = TextAreaField(
        'Descripción',
        validators=[
            DataRequired(message='La descripción es obligatoria'),
            Length(min=10, message='La descripción debe tener al menos 10 caracteres')
        ],
        render_kw={
            'placeholder': 'Descripción detallada del tipo de relación y cuándo utilizarla...',
            'rows': 5
        }
    )

    is_active = BooleanField(
        'Activo',
        default=True
    )


class ApiKeyForm(FlaskForm):
    """Form for creating/editing API keys."""
    service_name = SelectField(
        'Servicio',
        choices=[
            ('ipqualityscore', 'IPQualityScore (Email/Phone Validation)'),
            ('x_api', 'X API (Twitter)'),
            ('apify', 'Apify (Instagram, Web Scraping)'),
            ('openai', 'OpenAI (GPT-4 Vision - Análisis de Imágenes)'),
            ('deepseek', 'DeepSeek (VL - Análisis Visual Económico)'),
            ('serpapi', 'SerpAPI (Búsqueda Web - Google, DuckDuckGo)'),
            ('peopledatalabs', 'PeopleDataLabs (OSINT - Perfiles Sociales)'),
            ('other', 'Otro servicio')
        ],
        validators=[DataRequired(message='El servicio es obligatorio')],
        render_kw={'class': 'form-select'}
    )

    key_name = StringField(
        'Nombre de la API Key',
        validators=[
            DataRequired(message='El nombre es obligatorio'),
            Length(min=3, max=200, message='El nombre debe tener entre 3 y 200 caracteres')
        ],
        render_kw={'placeholder': 'Ej: IPQualityScore - Producción'}
    )

    api_key = PasswordField(
        'API Key',
        validators=[
            DataRequired(message='La API Key es obligatoria'),
            Length(min=10, message='La API Key debe tener al menos 10 caracteres')
        ],
        render_kw={
            'placeholder': 'Introduce la API Key del servicio',
            'autocomplete': 'off'
        }
    )

    description = TextAreaField(
        'Descripción (opcional)',
        validators=[Optional()],
        render_kw={
            'placeholder': 'Descripción del propósito de esta API Key...',
            'rows': 3
        }
    )

    is_active = BooleanField(
        'Activa',
        default=True,
        render_kw={'class': 'form-check-input'}
    )


class OSINTContactTypeConfigForm(FlaskForm):
    """Form for creating/editing an OSINT contact type configuration."""

    type_key = StringField(
        'Clave Interna (type_key)',
        validators=[
            DataRequired(message='La clave interna es obligatoria'),
            Length(min=2, max=50, message='Entre 2 y 50 caracteres'),
            Regexp(
                r'^[a-z0-9_]+$',
                message='Solo letras minúsculas, números y guiones bajos'
            ),
        ],
        render_kw={'placeholder': 'Ej: ip_address, mac_address'}
    )

    display_name = StringField(
        'Nombre a Mostrar',
        validators=[
            DataRequired(message='El nombre es obligatorio'),
            Length(min=2, max=100, message='El nombre debe tener entre 2 y 100 caracteres')
        ],
        render_kw={'placeholder': 'Ej: Correo Electrónico'}
    )

    description = TextAreaField(
        'Descripción',
        validators=[Optional()],
        render_kw={
            'rows': 3,
            'placeholder': 'Descripción del tipo de contacto...'
        }
    )

    icon_class = StringField(
        'Icono Bootstrap Icons',
        validators=[Optional(), Length(max=100)],
        render_kw={'placeholder': 'Ej: bi-envelope'}
    )

    color = SelectField(
        'Color',
        choices=[
            ('primary', 'Azul (primary)'),
            ('secondary', 'Gris (secondary)'),
            ('success', 'Verde (success)'),
            ('danger', 'Rojo (danger)'),
            ('warning', 'Amarillo (warning)'),
            ('info', 'Celeste (info)'),
            ('dark', 'Oscuro (dark)'),
        ],
        render_kw={'class': 'form-select'}
    )

    sort_order = IntegerField(
        'Orden de Visualización',
        validators=[
            DataRequired(message='El orden es obligatorio'),
            NumberRange(min=1, max=999, message='El orden debe estar entre 1 y 999')
        ],
        render_kw={'placeholder': '1'}
    )

    is_active = BooleanField(
        'Activo',
        default=True
    )
