"""Add database-level immutability triggers and cryptographic timestamps.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-01-22

This migration implements:
1. PostgreSQL triggers to enforce immutability on audit_logs and chain_of_custody tables
2. New columns for cryptographic timestamp signatures (HMAC)
3. Database functions that prevent UPDATE and DELETE operations

IMPORTANT: These triggers provide database-level protection that cannot be bypassed
by the application layer, ensuring forensic integrity for legal compliance.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    # ==========================================================================
    # 1. ADD CRYPTOGRAPHIC TIMESTAMP COLUMNS
    # ==========================================================================

    # Add timestamp signature column to audit_logs
    op.add_column('audit_logs', sa.Column('timestamp_signature', sa.String(128), nullable=True))
    op.add_column('audit_logs', sa.Column('record_hash', sa.String(64), nullable=True))

    # Add timestamp signature column to chain_of_custody
    op.add_column('chain_of_custody', sa.Column('timestamp_signature', sa.String(128), nullable=True))
    op.add_column('chain_of_custody', sa.Column('record_hash', sa.String(64), nullable=True))

    # ==========================================================================
    # 2. CREATE IMMUTABILITY TRIGGER FUNCTIONS
    # ==========================================================================

    # Function to prevent UPDATE on audit_logs
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_log_update()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'UPDATE operations on audit_logs table are forbidden. Audit logs are immutable for legal compliance (Ley 5/2014, UNE 71506).';
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Function to prevent DELETE on audit_logs
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_log_delete()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'DELETE operations on audit_logs table are forbidden. Audit logs are immutable for legal compliance (Ley 5/2014, UNE 71506).';
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Function to prevent UPDATE on chain_of_custody
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_chain_of_custody_update()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'UPDATE operations on chain_of_custody table are forbidden. Chain of custody records are immutable for forensic integrity (UNE 71506).';
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Function to prevent DELETE on chain_of_custody
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_chain_of_custody_delete()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'DELETE operations on chain_of_custody table are forbidden. Chain of custody records are immutable for forensic integrity (UNE 71506).';
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # ==========================================================================
    # 3. CREATE TRIGGERS
    # ==========================================================================

    # Triggers for audit_logs
    op.execute("""
        CREATE TRIGGER trigger_prevent_audit_log_update
        BEFORE UPDATE ON audit_logs
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_log_update();
    """)

    op.execute("""
        CREATE TRIGGER trigger_prevent_audit_log_delete
        BEFORE DELETE ON audit_logs
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_log_delete();
    """)

    # Triggers for chain_of_custody
    op.execute("""
        CREATE TRIGGER trigger_prevent_chain_of_custody_update
        BEFORE UPDATE ON chain_of_custody
        FOR EACH ROW
        EXECUTE FUNCTION prevent_chain_of_custody_update();
    """)

    op.execute("""
        CREATE TRIGGER trigger_prevent_chain_of_custody_delete
        BEFORE DELETE ON chain_of_custody
        FOR EACH ROW
        EXECUTE FUNCTION prevent_chain_of_custody_delete();
    """)

    # ==========================================================================
    # 4. CREATE AUDIT LOG FOR CASE IMMUTABLE FIELDS
    # ==========================================================================

    # Function to prevent modification of immutable case fields
    op.execute("""
        CREATE OR REPLACE FUNCTION protect_case_immutable_fields()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Protect numero_orden (case number)
            IF OLD.numero_orden IS DISTINCT FROM NEW.numero_orden THEN
                RAISE EXCEPTION 'Cannot modify numero_orden. Case numbers are immutable for legal compliance.';
            END IF;

            -- Protect fecha_inicio (start date) - only if it was set
            IF OLD.fecha_inicio IS NOT NULL AND OLD.fecha_inicio IS DISTINCT FROM NEW.fecha_inicio THEN
                RAISE EXCEPTION 'Cannot modify fecha_inicio once set. Investigation start dates are immutable.';
            END IF;

            -- Protect detective_tip (detective ID number)
            IF OLD.detective_tip IS NOT NULL AND OLD.detective_tip IS DISTINCT FROM NEW.detective_tip THEN
                RAISE EXCEPTION 'Cannot modify detective_tip once assigned. Detective TIP numbers are immutable for chain of responsibility.';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trigger_protect_case_immutable_fields
        BEFORE UPDATE ON cases
        FOR EACH ROW
        EXECUTE FUNCTION protect_case_immutable_fields();
    """)


def downgrade():
    # Remove triggers
    op.execute("DROP TRIGGER IF EXISTS trigger_prevent_audit_log_update ON audit_logs;")
    op.execute("DROP TRIGGER IF EXISTS trigger_prevent_audit_log_delete ON audit_logs;")
    op.execute("DROP TRIGGER IF EXISTS trigger_prevent_chain_of_custody_update ON chain_of_custody;")
    op.execute("DROP TRIGGER IF EXISTS trigger_prevent_chain_of_custody_delete ON chain_of_custody;")
    op.execute("DROP TRIGGER IF EXISTS trigger_protect_case_immutable_fields ON cases;")

    # Remove functions
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_update();")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_delete();")
    op.execute("DROP FUNCTION IF EXISTS prevent_chain_of_custody_update();")
    op.execute("DROP FUNCTION IF EXISTS prevent_chain_of_custody_delete();")
    op.execute("DROP FUNCTION IF EXISTS protect_case_immutable_fields();")

    # Remove columns
    op.drop_column('audit_logs', 'timestamp_signature')
    op.drop_column('audit_logs', 'record_hash')
    op.drop_column('chain_of_custody', 'timestamp_signature')
    op.drop_column('chain_of_custody', 'record_hash')
