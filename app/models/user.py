"""
User and Role models with MFA support.
"""
from datetime import datetime
from flask_login import UserMixin
from app.extensions import db, bcrypt
import pyotp


# Association table for many-to-many relationship
user_roles = db.Table('user_roles',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True)
)


class Role(db.Model):
    """User role model."""
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<Role {self.name}>'


class User(UserMixin, db.Model):
    """User model with MFA support."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)

    # Authentication
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    # Profile
    nombre = db.Column(db.String(200), nullable=False)
    apellidos = db.Column(db.String(200))
    tip_number = db.Column(db.String(20), unique=True, nullable=False)  # TIP (Tarjeta de Identidad Profesional)
    despacho = db.Column(db.String(200))  # Detective agency/office
    telefono = db.Column(db.String(20))

    # MFA (Multi-Factor Authentication)
    mfa_secret = db.Column(db.String(32))  # TOTP secret
    mfa_enabled = db.Column(db.Boolean, default=False)

    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    email_verified = db.Column(db.Boolean, default=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    # Relationships
    roles = db.relationship('Role', secondary=user_roles, backref=db.backref('users', lazy='dynamic'))

    def set_password(self, password):
        """Hash and set user password."""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        """Check if provided password matches hash."""
        return bcrypt.check_password_hash(self.password_hash, password)

    def generate_mfa_secret(self):
        """Generate a new MFA secret for TOTP."""
        self.mfa_secret = pyotp.random_base32()
        return self.mfa_secret

    def get_totp_uri(self):
        """Get TOTP URI for QR code generation."""
        if not self.mfa_secret:
            self.generate_mfa_secret()
        return pyotp.totp.TOTP(self.mfa_secret).provisioning_uri(
            name=self.email,
            issuer_name='Case Manager'
        )

    def verify_totp(self, token):
        """Verify TOTP token."""
        if not self.mfa_secret:
            return False
        totp = pyotp.TOTP(self.mfa_secret)
        return totp.verify(token, valid_window=1)

    def has_role(self, role_name):
        """Check if user has a specific role."""
        return any(role.name == role_name for role in self.roles)

    def is_admin(self):
        """Check if user is an administrator."""
        return self.has_role('admin')

    def is_detective(self):
        """Check if user is a detective."""
        return self.has_role('detective')

    def update_last_login(self):
        """Update last login timestamp."""
        self.last_login = datetime.utcnow()
        db.session.commit()

    def __repr__(self):
        return f'<User {self.email}>'

    # Flask-Login required properties
    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)
