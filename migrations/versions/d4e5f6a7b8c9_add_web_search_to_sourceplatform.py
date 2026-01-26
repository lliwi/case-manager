"""Add WEB_SEARCH to sourceplatform enum

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-01-19 17:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    """Add WEB_SEARCH value to sourceplatform enum."""
    # PostgreSQL allows adding values to existing enums
    op.execute("ALTER TYPE sourceplatform ADD VALUE IF NOT EXISTS 'WEB_SEARCH'")


def downgrade():
    """
    Note: PostgreSQL does not support removing values from enums directly.
    To properly downgrade, you would need to:
    1. Create a new enum without WEB_SEARCH
    2. Update the column to use the new enum
    3. Drop the old enum

    For safety, we leave the enum value in place during downgrade.
    """
    pass
