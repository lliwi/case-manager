"""
OSINT Contact Type Configuration model.

Stores display metadata (name, icon, color, description) and active status
for OSINT contact types. Built-in types (email, phone, social_profile,
username, other) are pre-populated and marked with is_builtin=True.
Administrators can create additional custom types and delete non-builtin ones.
"""
from datetime import datetime
from app.extensions import db


# Default configuration for the 5 built-in contact types (used as fallback)
BUILTIN_CONTACT_TYPES = [
    {
        'type_key': 'email',
        'display_name': 'Email',
        'description': 'Dirección de correo electrónico',
        'icon_class': 'bi-envelope',
        'color': 'primary',
        'sort_order': 1,
    },
    {
        'type_key': 'phone',
        'display_name': 'Teléfono',
        'description': 'Número de teléfono (fijo o móvil)',
        'icon_class': 'bi-telephone',
        'color': 'success',
        'sort_order': 2,
    },
    {
        'type_key': 'social_profile',
        'display_name': 'Perfil Social',
        'description': 'Perfil en redes sociales (URL o nombre de usuario)',
        'icon_class': 'bi-person-circle',
        'color': 'info',
        'sort_order': 3,
    },
    {
        'type_key': 'username',
        'display_name': 'Nombre de Usuario',
        'description': 'Nombre de usuario en plataformas digitales',
        'icon_class': 'bi-person-badge',
        'color': 'warning',
        'sort_order': 4,
    },
    {
        'type_key': 'other',
        'display_name': 'Otro',
        'description': 'Otro tipo de contacto o identificador digital',
        'icon_class': 'bi-info-circle',
        'color': 'secondary',
        'sort_order': 5,
    },
]


class OSINTContactTypeConfig(db.Model):
    """
    Configuration for OSINT contact type display and visibility.

    Built-in types are marked is_builtin=True; they can be edited but not
    deleted. Custom types created by admins have is_builtin=False and can
    be deleted if no contacts use them.
    """
    __tablename__ = 'osint_contact_type_configs'

    id = db.Column(db.Integer, primary_key=True)

    # Unique key stored in OSINTContact.contact_type (max 50 chars)
    type_key = db.Column(db.String(50), unique=True, nullable=False, index=True)

    # Display metadata
    display_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    icon_class = db.Column(db.String(100), nullable=False, default='bi-info-circle')
    color = db.Column(db.String(50), nullable=False, default='secondary')

    # Visibility and ordering
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=99, nullable=False)

    # Built-in types can be edited but not deleted
    is_builtin = db.Column(db.Boolean, default=False, nullable=False)

    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    created_by = db.relationship('User', foreign_keys=[created_by_id])

    def __repr__(self):
        return f'<OSINTContactTypeConfig {self.type_key}>'

    # ------------------------------------------------------------------
    # Class-level helpers used by forms and templates
    # ------------------------------------------------------------------

    @classmethod
    def get_active_choices(cls):
        """
        Return [(type_key, display_name)] for active types ordered by sort_order.
        Falls back to built-in defaults if the table is empty.
        """
        configs = cls.query.filter_by(is_active=True).order_by(cls.sort_order).all()
        if configs:
            return [(c.type_key, c.display_name) for c in configs]
        return [(t['type_key'], t['display_name']) for t in BUILTIN_CONTACT_TYPES]

    @classmethod
    def get_all_choices(cls):
        """
        Return all [(type_key, display_name)] ordered by sort_order.
        Useful for edit/filter dropdowns that need to show inactive types.
        """
        configs = cls.query.order_by(cls.sort_order).all()
        if configs:
            return [(c.type_key, c.display_name) for c in configs]
        return [(t['type_key'], t['display_name']) for t in BUILTIN_CONTACT_TYPES]

    @classmethod
    def get_config(cls, type_key):
        """Get the config row for a given type key, or None."""
        return cls.query.filter_by(type_key=type_key).first()

    @classmethod
    def get_icon(cls, type_key):
        """Return the Bootstrap icon class for a type key."""
        config = cls.query.filter_by(type_key=type_key).first()
        if config:
            return config.icon_class
        for t in BUILTIN_CONTACT_TYPES:
            if t['type_key'] == type_key:
                return t['icon_class']
        return 'bi-info-circle'

    def contact_count(self):
        """Return the number of non-deleted OSINTContacts using this type."""
        from app.models.osint_contact import OSINTContact
        return OSINTContact.query.filter_by(
            contact_type=self.type_key, is_deleted=False
        ).count()
