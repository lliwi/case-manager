"""Add last_result_timestamp to monitoring_sources

Revision ID: c3d4e5f6a7b8
Revises: b7c8d9e0f1a2
Create Date: 2026-01-18 13:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b8'
down_revision = 'b7c8d9e0f1a2'
branch_labels = None
depends_on = None


def upgrade():
    # Add last_result_timestamp column to monitoring_sources
    op.add_column('monitoring_sources',
        sa.Column('last_result_timestamp', sa.DateTime(), nullable=True)
    )


def downgrade():
    # Remove last_result_timestamp column
    op.drop_column('monitoring_sources', 'last_result_timestamp')
