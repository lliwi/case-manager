"""add soft-delete columns to users

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-07

Users are soft-deleted (never hard-deleted) so the audit trail and historical
references remain intact.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('is_deleted', sa.Boolean(), nullable=False,
                                     server_default=sa.false()))
    op.add_column('users', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('deleted_by_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_users_deleted_by_id_users', 'users', 'users',
        ['deleted_by_id'], ['id'],
    )


def downgrade():
    op.drop_constraint('fk_users_deleted_by_id_users', 'users', type_='foreignkey')
    op.drop_column('users', 'deleted_by_id')
    op.drop_column('users', 'deleted_at')
    op.drop_column('users', 'is_deleted')
