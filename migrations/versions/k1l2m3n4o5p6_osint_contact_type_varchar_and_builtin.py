"""Convert osint_contacts.contact_type from enum to varchar and add is_builtin to configs.

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-02-20

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'k1l2m3n4o5p6'
down_revision = 'j0k1l2m3n4o5'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Change contact_type from enum to varchar so custom types can be stored
    op.execute(
        "ALTER TABLE osint_contacts "
        "ALTER COLUMN contact_type TYPE VARCHAR(50) USING contact_type::text"
    )
    # Drop the now-unused enum type
    op.execute("DROP TYPE IF EXISTS osint_contact_type_enum")

    # 2. Add is_builtin flag to config table
    op.add_column(
        'osint_contact_type_configs',
        sa.Column('is_builtin', sa.Boolean(), nullable=False, server_default='false'),
    )
    # Mark all existing rows (the 5 built-in types) as builtin
    op.execute("UPDATE osint_contact_type_configs SET is_builtin = true")


def downgrade():
    # Restore is_builtin column removal
    op.drop_column('osint_contact_type_configs', 'is_builtin')

    # Re-create enum and restore column type
    op.execute(
        "CREATE TYPE osint_contact_type_enum AS ENUM "
        "('email', 'phone', 'social_profile', 'username', 'other')"
    )
    op.execute(
        "ALTER TABLE osint_contacts "
        "ALTER COLUMN contact_type TYPE osint_contact_type_enum "
        "USING contact_type::osint_contact_type_enum"
    )
