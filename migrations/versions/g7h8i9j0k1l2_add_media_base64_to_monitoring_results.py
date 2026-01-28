"""Add media_base64 column to monitoring_results table.

Revision ID: g7h8i9j0k1l2
Revises: f6a7b8c9d0e1
Create Date: 2026-01-28

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g7h8i9j0k1l2'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade():
    """Add media_base64 column for storing base64-encoded images."""
    op.add_column(
        'monitoring_results',
        sa.Column('media_base64', sa.JSON(), nullable=True)
    )


def downgrade():
    """Remove media_base64 column."""
    op.drop_column('monitoring_results', 'media_base64')
