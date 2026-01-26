"""make audit_log user_id nullable

Revision ID: f6a7b8c9d0e1
Revises: a1b2c3d4e5f6
Create Date: 2026-01-26 17:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f6a7b8c9d0e1'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    """Make user_id and user_email nullable for anonymous audit events."""
    # Drop the NOT NULL constraint on user_id
    op.alter_column('audit_logs', 'user_id',
                    existing_type=sa.Integer(),
                    nullable=True)

    # Drop the NOT NULL constraint on user_email
    op.alter_column('audit_logs', 'user_email',
                    existing_type=sa.String(length=120),
                    nullable=True)


def downgrade():
    """Restore NOT NULL constraints (will fail if NULL values exist)."""
    op.alter_column('audit_logs', 'user_id',
                    existing_type=sa.Integer(),
                    nullable=False)

    op.alter_column('audit_logs', 'user_email',
                    existing_type=sa.String(length=120),
                    nullable=False)
