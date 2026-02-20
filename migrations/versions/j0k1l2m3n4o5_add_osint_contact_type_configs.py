"""Add osint_contact_type_configs table.

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-02-20

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = 'j0k1l2m3n4o5'
down_revision = 'i9j0k1l2m3n4'
branch_labels = None
depends_on = None


BUILTIN_TYPES = [
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


def upgrade():
    t = op.create_table(
        'osint_contact_type_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('type_key', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('icon_class', sa.String(length=100), nullable=False,
                  server_default='bi-info-circle'),
        sa.Column('color', sa.String(length=50), nullable=False,
                  server_default='secondary'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='99'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_by_id', sa.Integer(),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('type_key', name='uq_osint_contact_type_configs_type_key'),
    )
    op.create_index(
        'ix_osint_contact_type_configs_type_key',
        'osint_contact_type_configs',
        ['type_key'],
    )

    now = datetime.utcnow()
    op.bulk_insert(
        t,
        [
            {
                'type_key': bt['type_key'],
                'display_name': bt['display_name'],
                'description': bt['description'],
                'icon_class': bt['icon_class'],
                'color': bt['color'],
                'is_active': True,
                'sort_order': bt['sort_order'],
                'created_at': now,
                'updated_at': None,
                'created_by_id': None,
            }
            for bt in BUILTIN_TYPES
        ],
    )


def downgrade():
    op.drop_index(
        'ix_osint_contact_type_configs_type_key',
        table_name='osint_contact_type_configs',
    )
    op.drop_table('osint_contact_type_configs')
