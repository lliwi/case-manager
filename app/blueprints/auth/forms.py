"""
Authentication forms.
"""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from app.models.user import User


class LoginForm(FlaskForm):
    """User login form."""
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    remember_me = BooleanField('Recordarme')
    submit = SubmitField('Iniciar Sesión')


class MFAVerificationForm(FlaskForm):
    """MFA verification form."""
    token = StringField('Código de Verificación', validators=[
        DataRequired(),
        Length(min=6, max=6, message='El código debe tener 6 dígitos')
    ])
    submit = SubmitField('Verificar')


class SetupMFAForm(FlaskForm):
    """MFA setup form."""
    token = StringField('Código de Verificación', validators=[
        DataRequired(),
        Length(min=6, max=6, message='El código debe tener 6 dígitos')
    ])
    submit = SubmitField('Activar MFA')


class RegistrationForm(FlaskForm):
    """User registration form (for admins to create users)."""
    email = StringField('Email', validators=[DataRequired(), Email()])
    nombre = StringField('Nombre', validators=[DataRequired(), Length(min=2, max=200)])
    apellidos = StringField('Apellidos', validators=[Length(max=200)])
    tip_number = StringField('Número TIP', validators=[DataRequired(), Length(max=20)])
    password = PasswordField('Contraseña', validators=[
        DataRequired(),
        Length(min=8, message='La contraseña debe tener al menos 8 caracteres')
    ])
    password_confirm = PasswordField('Confirmar Contraseña', validators=[
        DataRequired(),
        EqualTo('password', message='Las contraseñas deben coincidir')
    ])
    submit = SubmitField('Crear Usuario')

    def validate_email(self, email):
        """Check if email already exists."""
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Este email ya está registrado.')

    def validate_tip_number(self, tip_number):
        """Check if TIP number already exists."""
        user = User.query.filter_by(tip_number=tip_number.data).first()
        if user:
            raise ValidationError('Este número TIP ya está registrado.')


class ProfileForm(FlaskForm):
    """User profile edit form."""
    nombre = StringField('Nombre', validators=[DataRequired(), Length(min=2, max=200)])
    apellidos = StringField('Apellidos', validators=[Length(max=200)])
    despacho = StringField('Despacho', validators=[Length(max=200)])
    telefono = StringField('Teléfono', validators=[Length(max=20)])
    submit = SubmitField('Guardar Cambios')


class ChangePasswordForm(FlaskForm):
    """Change password form."""
    current_password = PasswordField('Contraseña Actual', validators=[DataRequired()])
    new_password = PasswordField('Nueva Contraseña', validators=[
        DataRequired(),
        Length(min=8, message='La contraseña debe tener al menos 8 caracteres')
    ])
    confirm_password = PasswordField('Confirmar Nueva Contraseña', validators=[
        DataRequired(),
        EqualTo('new_password', message='Las contraseñas deben coincidir')
    ])
    submit = SubmitField('Cambiar Contraseña')
