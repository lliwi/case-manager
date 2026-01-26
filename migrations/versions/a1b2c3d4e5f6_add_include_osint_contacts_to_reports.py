"""Add include_osint_contacts to reports table

Revision ID: a1b2c3d4e5f6
Revises: f12d06e18f99
Create Date: 2026-01-16 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'dda01fbc3d5e'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add include_osint_contacts column to reports table.

    This migration adds the column for existing installations.
    New installations will have this column from the initial migration.
    """
    # Check if the column already exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Get existing columns in reports table
    columns = [col['name'] for col in inspector.get_columns('reports')]

    # Only add if column doesn't exist
    if 'include_osint_contacts' not in columns:
        op.add_column('reports',
            sa.Column('include_osint_contacts', sa.Boolean(),
                     nullable=False, server_default='false'))


def downgrade():
    """Remove include_osint_contacts column from reports table."""
    op.drop_column('reports', 'include_osint_contacts')
