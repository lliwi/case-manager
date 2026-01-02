"""
Evidence forms.
"""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, TextAreaField, DateTimeField, SelectField, DecimalField
from wtforms.validators import DataRequired, Optional, Length, NumberRange
from datetime import datetime


class EvidenceUploadForm(FlaskForm):
    """Form for uploading evidence."""

    file = FileField(
        'Archivo de Evidencia',
        validators=[FileRequired('Debe seleccionar un archivo')],
        description='Seleccione el archivo de evidencia a subir'
    )

    description = TextAreaField(
        'Descripción',
        validators=[DataRequired('La descripción es obligatoria'), Length(max=1000)],
        description='Descripción detallada de la evidencia'
    )

    tags = StringField(
        'Etiquetas',
        validators=[Optional(), Length(max=500)],
        description='Etiquetas separadas por comas (ej: vigilancia, foto, coche)'
    )

    # Acquisition metadata
    acquisition_date = DateTimeField(
        'Fecha de Adquisición',
        validators=[Optional()],
        format='%Y-%m-%d %H:%M:%S',
        default=datetime.utcnow,
        description='Fecha y hora de adquisición de la evidencia'
    )

    acquisition_method = SelectField(
        'Método de Adquisición',
        choices=[
            ('Direct upload', 'Subida directa'),
            ('Camera', 'Cámara fotográfica'),
            ('Screen capture', 'Captura de pantalla'),
            ('Physical copy', 'Copia física'),
            ('Network capture', 'Captura de red'),
            ('Disk imaging', 'Imagen de disco'),
            ('Mobile extraction', 'Extracción móvil'),
            ('Social media download', 'Descarga redes sociales'),
            ('Email export', 'Exportación email'),
            ('Other', 'Otro')
        ],
        default='Direct upload',
        validators=[DataRequired()]
    )

    source_device = StringField(
        'Dispositivo de Origen',
        validators=[Optional(), Length(max=200)],
        description='Dispositivo del que se obtuvo (ej: iPhone 12, Dell Laptop)'
    )

    source_location = StringField(
        'Ubicación de Origen',
        validators=[Optional(), Length(max=200)],
        description='Ubicación física o digital de origen'
    )

    # Geolocation (if available)
    latitude = DecimalField(
        'Latitud',
        validators=[Optional(), NumberRange(-90, 90)],
        places=6,
        description='Latitud GPS (si disponible)'
    )

    longitude = DecimalField(
        'Longitud',
        validators=[Optional(), NumberRange(-180, 180)],
        places=6,
        description='Longitud GPS (si disponible)'
    )

    acquisition_notes = TextAreaField(
        'Notas de Adquisición',
        validators=[Optional(), Length(max=2000)],
        description='Notas adicionales sobre la adquisición de la evidencia'
    )


class EvidenceSearchForm(FlaskForm):
    """Form for searching evidence."""

    query = StringField(
        'Buscar',
        validators=[Optional(), Length(max=200)],
        description='Buscar en nombre, descripción o etiquetas'
    )

    evidence_type = SelectField(
        'Tipo',
        choices=[
            ('', 'Todos los tipos'),
            ('IMAGEN', 'Imagen'),
            ('VIDEO', 'Video'),
            ('AUDIO', 'Audio'),
            ('DOCUMENTO', 'Documento'),
            ('EMAIL', 'Email'),
            ('CAPTURA_WEB', 'Captura Web'),
            ('DATOS_DIGITALES', 'Datos Digitales'),
            ('OTROS', 'Otros')
        ],
        default='',
        validators=[Optional()]
    )

    integrity_status = SelectField(
        'Estado de Integridad',
        choices=[
            ('', 'Todos'),
            ('verified', 'Verificada'),
            ('unverified', 'No verificada'),
            ('failed', 'Fallida')
        ],
        default='',
        validators=[Optional()]
    )

    date_from = DateTimeField(
        'Desde',
        validators=[Optional()],
        format='%Y-%m-%d',
        description='Fecha inicio'
    )

    date_to = DateTimeField(
        'Hasta',
        validators=[Optional()],
        format='%Y-%m-%d',
        description='Fecha fin'
    )
