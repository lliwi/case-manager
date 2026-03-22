"""Add vehicle OSINT contact type.

Revision ID: a2b3c4d5e6f7
Revises: 3e1ebb1401dc
Create Date: 2026-03-22

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = 'a2b3c4d5e6f7'
down_revision = '3e1ebb1401dc'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT id FROM osint_contact_type_configs WHERE type_key = 'vehicle'")
    )
    if result.fetchone() is None:
        conn.execute(
            sa.text(
                "INSERT INTO osint_contact_type_configs "
                "(type_key, display_name, description, icon_class, color, is_active, sort_order, is_builtin, created_at) "
                "VALUES (:tk, :dn, :desc, :ic, :col, true, :so, true, :now)"
            ),
            {
                'tk': 'vehicle',
                'dn': 'Vehículo (Matrícula / VIN)',
                'desc': 'Matrícula española o número de bastidor (VIN) de un vehículo',
                'ic': 'bi-car-front',
                'col': 'info',
                'so': 5,
                'now': datetime.utcnow(),
            },
        )
        # Push 'other' to sort_order 6
        conn.execute(
            sa.text(
                "UPDATE osint_contact_type_configs SET sort_order = 6 WHERE type_key = 'other'"
            )
        )


def downgrade():
    op.execute("DELETE FROM osint_contact_type_configs WHERE type_key = 'vehicle'")
    op.execute(
        "UPDATE osint_contact_type_configs SET sort_order = 5 WHERE type_key = 'other'"
    )
