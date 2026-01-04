"""
Graph forms for creating nodes and relationships.
"""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, DecimalField, DateField
from wtforms.validators import DataRequired, Optional, Length, Email, NumberRange


class PersonNodeForm(FlaskForm):
    """Form for creating/editing Person nodes."""

    name = StringField(
        'Nombre Completo',
        validators=[DataRequired('El nombre es obligatorio'), Length(max=200)],
        description='Nombre completo de la persona'
    )

    dni_cif = StringField(
        'DNI/NIE',
        validators=[Optional(), Length(max=20)],
        description='DNI o NIE (será validado)'
    )

    birth_date = DateField(
        'Fecha de Nacimiento',
        validators=[Optional()],
        description='Fecha de nacimiento'
    )

    gender = SelectField(
        'Género',
        choices=[('', 'No especificado'), ('M', 'Masculino'), ('F', 'Femenino'), ('O', 'Otro')],
        default='',
        validators=[Optional()]
    )

    occupation = StringField(
        'Profesión',
        validators=[Optional(), Length(max=200)],
        description='Profesión u ocupación'
    )

    notes = TextAreaField(
        'Notas',
        validators=[Optional(), Length(max=2000)],
        description='Notas adicionales sobre la persona'
    )


class CompanyNodeForm(FlaskForm):
    """Form for creating/editing Company nodes."""

    name = StringField(
        'Nombre de Empresa',
        validators=[DataRequired('El nombre de empresa es obligatorio'), Length(max=200)],
        description='Nombre de la empresa'
    )

    cif = StringField(
        'CIF',
        validators=[Optional(), Length(max=20)],
        description='CIF de la empresa (será validado)'
    )

    industry = StringField(
        'Sector',
        validators=[Optional(), Length(max=200)],
        description='Sector o industria'
    )

    address = StringField(
        'Dirección',
        validators=[Optional(), Length(max=500)],
        description='Dirección de la empresa'
    )

    notes = TextAreaField(
        'Notas',
        validators=[Optional(), Length(max=2000)],
        description='Notas adicionales sobre la empresa'
    )


class PhoneNodeForm(FlaskForm):
    """Form for creating/editing Phone nodes."""

    number = StringField(
        'Número de Teléfono',
        validators=[DataRequired('El número de teléfono es obligatorio'), Length(max=50)],
        description='Número de teléfono completo con prefijo'
    )

    carrier = StringField(
        'Operadora',
        validators=[Optional(), Length(max=100)],
        description='Compañía operadora'
    )

    phone_type = SelectField(
        'Tipo',
        choices=[
            ('', 'No especificado'),
            ('mobile', 'Móvil'),
            ('landline', 'Fijo'),
            ('voip', 'VoIP')
        ],
        default='',
        validators=[Optional()]
    )

    notes = TextAreaField(
        'Notas',
        validators=[Optional(), Length(max=2000)],
        description='Notas adicionales sobre el teléfono'
    )


class EmailNodeForm(FlaskForm):
    """Form for creating/editing Email nodes."""

    address = StringField(
        'Dirección de Email',
        validators=[DataRequired('El email es obligatorio'), Email(), Length(max=200)],
        description='Dirección de correo electrónico'
    )

    provider = StringField(
        'Proveedor',
        validators=[Optional(), Length(max=100)],
        description='Proveedor de email (Gmail, Outlook, etc.)'
    )

    notes = TextAreaField(
        'Notas',
        validators=[Optional(), Length(max=2000)],
        description='Notas adicionales sobre el email'
    )


class VehicleNodeForm(FlaskForm):
    """Form for creating/editing Vehicle nodes."""

    plate = StringField(
        'Matrícula',
        validators=[DataRequired('La matrícula es obligatoria'), Length(max=20)],
        description='Matrícula del vehículo'
    )

    make = StringField(
        'Marca',
        validators=[Optional(), Length(max=100)],
        description='Marca del vehículo'
    )

    model = StringField(
        'Modelo',
        validators=[Optional(), Length(max=100)],
        description='Modelo del vehículo'
    )

    color = StringField(
        'Color',
        validators=[Optional(), Length(max=50)],
        description='Color del vehículo'
    )

    year = StringField(
        'Año',
        validators=[Optional(), Length(max=4)],
        description='Año de fabricación'
    )

    notes = TextAreaField(
        'Notas',
        validators=[Optional(), Length(max=2000)],
        description='Notas adicionales sobre el vehículo'
    )


class AddressNodeForm(FlaskForm):
    """Form for creating/editing Address nodes."""

    street = StringField(
        'Calle',
        validators=[DataRequired('La calle es obligatoria'), Length(max=500)],
        description='Calle y número'
    )

    city = StringField(
        'Ciudad',
        validators=[DataRequired('La ciudad es obligatoria'), Length(max=200)],
        description='Ciudad'
    )

    postal_code = StringField(
        'Código Postal',
        validators=[Optional(), Length(max=10)],
        description='Código postal'
    )

    province = StringField(
        'Provincia',
        validators=[Optional(), Length(max=200)],
        description='Provincia'
    )

    country = StringField(
        'País',
        validators=[Optional(), Length(max=200)],
        default='España',
        description='País'
    )

    latitude = DecimalField(
        'Latitud',
        validators=[Optional(), NumberRange(-90, 90)],
        places=6,
        description='Latitud GPS'
    )

    longitude = DecimalField(
        'Longitud',
        validators=[Optional(), NumberRange(-180, 180)],
        places=6,
        description='Longitud GPS'
    )

    notes = TextAreaField(
        'Notas',
        validators=[Optional(), Length(max=2000)],
        description='Notas adicionales sobre la dirección'
    )


class SocialProfileNodeForm(FlaskForm):
    """Form for creating/editing Social Profile nodes."""

    platform = SelectField(
        'Plataforma',
        choices=[
            ('Facebook', 'Facebook'),
            ('Twitter', 'Twitter / X'),
            ('Instagram', 'Instagram'),
            ('LinkedIn', 'LinkedIn'),
            ('TikTok', 'TikTok'),
            ('YouTube', 'YouTube'),
            ('Telegram', 'Telegram'),
            ('WhatsApp', 'WhatsApp'),
            ('Other', 'Otra')
        ],
        validators=[DataRequired('La plataforma es obligatoria')]
    )

    username = StringField(
        'Usuario',
        validators=[DataRequired('El nombre de usuario es obligatorio'), Length(max=200)],
        description='Nombre de usuario o handle'
    )

    url = StringField(
        'URL del Perfil',
        validators=[Optional(), Length(max=500)],
        description='URL completa del perfil'
    )

    display_name = StringField(
        'Nombre Mostrado',
        validators=[Optional(), Length(max=200)],
        description='Nombre que se muestra en el perfil'
    )

    followers = StringField(
        'Seguidores',
        validators=[Optional(), Length(max=50)],
        description='Número de seguidores'
    )

    notes = TextAreaField(
        'Notas',
        validators=[Optional(), Length(max=2000)],
        description='Notas adicionales sobre el perfil'
    )


class RelationshipForm(FlaskForm):
    """Form for creating relationships between nodes."""

    from_node_id = StringField(
        'Nodo Origen',
        validators=[DataRequired('El nodo origen es obligatorio')],
        description='ID del nodo origen'
    )

    to_node_id = StringField(
        'Nodo Destino',
        validators=[DataRequired('El nodo destino es obligatorio')],
        description='ID del nodo destino'
    )

    relationship_type = SelectField(
        'Tipo de Relación',
        choices=[],  # Will be populated dynamically
        validators=[DataRequired('El tipo de relación es obligatorio')]
    )

    def __init__(self, *args, **kwargs):
        """Initialize form and load relationship types dynamically."""
        super(RelationshipForm, self).__init__(*args, **kwargs)

        # Load base relationship types from enum
        from app.models.graph import RelationshipType
        base_choices = [
            ('FAMILIAR_DE', 'Familiar de'),
            ('SOCIO_DE', 'Socio de'),
            ('EMPLEADO_DE', 'Empleado de'),
            ('UTILIZA_TELEFONO', 'Utiliza teléfono'),
            ('UTILIZA_EMAIL', 'Utiliza email'),
            ('UTILIZA_VEHICULO', 'Utiliza vehículo'),
            ('PROPIETARIO_DE', 'Propietario de'),
            ('RESIDE_EN', 'Reside en'),
            ('VISTO_EN', 'Visto en'),
            ('CONTACTO_CON', 'Contacto con'),
            ('VINCULADO_A_EVIDENCIA', 'Vinculado a evidencia'),
            ('PERFIL_DE', 'Perfil de'),
            ('TITULAR_DE', 'Titular de'),
            ('TRANSFERENCIA_A', 'Transferencia a'),
            ('CONEXION_DESDE', 'Conexión desde')
        ]

        # Load custom relationship types
        from app.models.relationship_type_custom import RelationshipTypeCustom
        custom_types = RelationshipTypeCustom.query.filter_by(
            is_deleted=False,
            is_active=True
        ).order_by(RelationshipTypeCustom.name).all()

        custom_choices = [(ct.name, ct.label) for ct in custom_types]

        # Combine both lists (base first, then custom)
        self.relationship_type.choices = base_choices + custom_choices

    confidence = DecimalField(
        'Confianza',
        validators=[Optional(), NumberRange(0, 1)],
        places=2,
        default=1.0,
        description='Nivel de confianza (0.0 a 1.0)'
    )

    start_date = DateField(
        'Fecha Inicio',
        validators=[Optional()],
        description='Fecha de inicio de la relación'
    )

    end_date = DateField(
        'Fecha Fin',
        validators=[Optional()],
        description='Fecha de fin de la relación (si aplica)'
    )

    notes = TextAreaField(
        'Notas',
        validators=[Optional(), Length(max=2000)],
        description='Notas adicionales sobre la relación'
    )


class GraphSearchForm(FlaskForm):
    """Form for searching the graph."""

    query = StringField(
        'Buscar',
        validators=[Optional(), Length(max=200)],
        description='Buscar nodos por nombre, DNI, teléfono, etc.'
    )

    node_type = SelectField(
        'Tipo de Nodo',
        choices=[
            ('', 'Todos'),
            ('Person', 'Persona'),
            ('Company', 'Empresa'),
            ('Phone', 'Teléfono'),
            ('Email', 'Email'),
            ('Vehicle', 'Vehículo'),
            ('Address', 'Dirección'),
            ('SocialProfile', 'Perfil Social'),
            ('Evidence', 'Evidencia')
        ],
        default='',
        validators=[Optional()]
    )
