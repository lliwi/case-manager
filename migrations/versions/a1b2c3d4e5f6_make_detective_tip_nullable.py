"""make cases.detective_tip nullable (TIP is optional)

Revision ID: a1b2c3d4e5f6
Revises: 936860c27134
Create Date: 2026-06-07

The detective's TIP (Tarjeta de Identidad Profesional) is optional, so the
denormalized cases.detective_tip column must allow NULL values.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '936860c27134'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        'cases',
        'detective_tip',
        existing_type=sa.String(length=20),
        nullable=True,
    )


def downgrade():
    op.alter_column(
        'cases',
        'detective_tip',
        existing_type=sa.String(length=20),
        nullable=False,
    )
