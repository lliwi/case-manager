"""Add DOCX file fields to reports table.

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-02-01

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'i9j0k1l2m3n4'
down_revision = 'h8i9j0k1l2m3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('reports', sa.Column('docx_file_path', sa.String(500), nullable=True))
    op.add_column('reports', sa.Column('docx_file_size', sa.Integer(), nullable=True))
    op.add_column('reports', sa.Column('docx_file_hash_sha256', sa.String(64), nullable=True))
    op.add_column('reports', sa.Column('docx_file_hash_sha512', sa.String(128), nullable=True))


def downgrade():
    op.drop_column('reports', 'docx_file_hash_sha512')
    op.drop_column('reports', 'docx_file_hash_sha256')
    op.drop_column('reports', 'docx_file_size')
    op.drop_column('reports', 'docx_file_path')
