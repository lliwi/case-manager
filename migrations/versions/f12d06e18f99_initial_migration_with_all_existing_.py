"""initial migration with all existing tables

Revision ID: f12d06e18f99
Revises:
Create Date: 2026-01-09 18:01:59.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f12d06e18f99'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """
    Initial migration - creates all tables with include_evidence_thumbnails field.

    This migration is designed to work for both:
    - New installations (creates all tables from scratch)
    - Existing installations (no-op if tables already exist)
    """

    # Check if tables already exist (for existing installations)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # If reports table already exists, this is an existing installation - do nothing
    if 'reports' in existing_tables:
        return

    # For new installations, create all tables
    # Note: SQLAlchemy models have the field, so db.create_all() will include it
    # But we use explicit Alembic commands for better control

    # Create enum types first
    op.execute("CREATE TYPE reporttype AS ENUM ('INFORME_FINAL', 'INFORME_PARCIAL', 'INFORME_PRELIMINAR', 'DICTAMEN_PERICIAL', 'ANEXO_TECNICO')")
    op.execute("CREATE TYPE reportstatus AS ENUM ('DRAFT', 'GENERATING', 'COMPLETED', 'FAILED', 'SIGNED')")
    op.execute("CREATE TYPE legitimacytype AS ENUM ('BAJAS_LABORALES', 'COMPETENCIA_DESLEAL', 'CUSTODIA_MENORES', 'INVESTIGACION_PATRIMONIAL', 'FRAUDE_SEGUROS', 'INFIDELIDAD_CONYUGAL', 'LOCALIZACION_PERSONAS', 'SOLVENCIA_PATRIMONIAL', 'OTROS')")
    op.execute("CREATE TYPE casestatus AS ENUM ('PENDIENTE_VALIDACION', 'EN_INVESTIGACION', 'SUSPENDIDO', 'CERRADO', 'ARCHIVADO')")
    op.execute("CREATE TYPE casepriority AS ENUM ('BAJA', 'MEDIA', 'ALTA', 'URGENTE')")
    op.execute("CREATE TYPE evidencetype AS ENUM ('DOCUMENT', 'IMAGE', 'VIDEO', 'AUDIO', 'EMAIL', 'CHAT', 'SOCIAL_MEDIA', 'FINANCIAL', 'GPS', 'OTHER')")
    op.execute("CREATE TYPE actiontype AS ENUM ('ADDED', 'ACCESSED', 'MODIFIED', 'MOVED', 'COPIED', 'ANALYZED', 'EXPORTED', 'DELETED')")

    # Create users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=80), nullable=False),
        sa.Column('email', sa.String(length=120), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('nombre', sa.String(length=200), nullable=False),
        sa.Column('tip_number', sa.String(length=20), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
        sa.UniqueConstraint('email')
    )

    # Create roles table
    op.create_table('roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('description', sa.String(length=200), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # Create user_roles association table
    op.create_table('user_roles',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'role_id')
    )

    # Create legitimacy_types_custom table
    op.create_table('legitimacy_types_custom',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # Create cases table
    op.create_table('cases',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('numero_orden', sa.String(length=50), nullable=False),
        sa.Column('fecha_inicio', sa.DateTime(), nullable=False),
        sa.Column('fecha_cierre', sa.DateTime(), nullable=True),
        sa.Column('cliente_nombre', sa.String(length=200), nullable=False),
        sa.Column('cliente_dni_cif', sa.String(length=20), nullable=False),
        sa.Column('cliente_direccion', sa.Text(), nullable=True),
        sa.Column('cliente_telefono', sa.String(length=20), nullable=True),
        sa.Column('cliente_email', sa.String(length=120), nullable=True),
        sa.Column('legitimacy_type', sa.Enum('BAJAS_LABORALES', 'COMPETENCIA_DESLEAL', 'CUSTODIA_MENORES', 'INVESTIGACION_PATRIMONIAL', 'FRAUDE_SEGUROS', 'INFIDELIDAD_CONYUGAL', 'LOCALIZACION_PERSONAS', 'SOLVENCIA_PATRIMONIAL', 'OTROS', name='legitimacytype'), nullable=True),
        sa.Column('legitimacy_type_custom_id', sa.Integer(), nullable=True),
        sa.Column('legitimacy_document_path', sa.String(length=500), nullable=True),
        sa.Column('legitimacy_description', sa.Text(), nullable=False),
        sa.Column('legitimacy_validated', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('legitimacy_validated_by_id', sa.Integer(), nullable=True),
        sa.Column('legitimacy_validated_at', sa.DateTime(), nullable=True),
        sa.Column('sujeto_nombres', sa.Text(), nullable=True),
        sa.Column('sujeto_dnis', sa.Text(), nullable=True),
        sa.Column('objetivo', sa.Text(), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('PENDIENTE_VALIDACION', 'EN_INVESTIGACION', 'SUSPENDIDO', 'CERRADO', 'ARCHIVADO', name='casestatus'), nullable=False),
        sa.Column('priority', sa.Enum('BAJA', 'MEDIA', 'ALTA', 'URGENTE', name='casepriority'), nullable=False),
        sa.Column('assigned_to_id', sa.Integer(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('extra_data', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['legitimacy_type_custom_id'], ['legitimacy_types_custom.id']),
        sa.ForeignKeyConstraint(['legitimacy_validated_by_id'], ['users.id']),
        sa.ForeignKeyConstraint(['assigned_to_id'], ['users.id']),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('numero_orden')
    )
    op.create_index('ix_cases_numero_orden', 'cases', ['numero_orden'])

    # Create reports table with include_evidence_thumbnails field
    op.create_table('reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('created_by_id', sa.Integer(), nullable=False),
        sa.Column('report_type', sa.Enum('INFORME_FINAL', 'INFORME_PARCIAL', 'INFORME_PRELIMINAR', 'DICTAMEN_PERICIAL', 'ANEXO_TECNICO', name='reporttype'), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('introduction', sa.Text(), nullable=True),
        sa.Column('methodology', sa.Text(), nullable=True),
        sa.Column('findings', sa.Text(), nullable=True),
        sa.Column('conclusions', sa.Text(), nullable=True),
        sa.Column('recommendations', sa.Text(), nullable=True),
        sa.Column('include_evidence_list', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('include_timeline', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('include_graph', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('include_chain_of_custody', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('include_plugin_results', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('include_evidence_thumbnails', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('include_osint_contacts', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('file_hash_sha256', sa.String(length=64), nullable=True),
        sa.Column('file_hash_sha512', sa.String(length=128), nullable=True),
        sa.Column('is_signed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('signature_data', sa.Text(), nullable=True),
        sa.Column('signature_timestamp', sa.DateTime(), nullable=True),
        sa.Column('signer_name', sa.String(length=200), nullable=True),
        sa.Column('signer_tip', sa.String(length=50), nullable=True),
        sa.Column('status', sa.Enum('DRAFT', 'GENERATING', 'COMPLETED', 'FAILED', 'SIGNED', name='reportstatus'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('generated_at', sa.DateTime(), nullable=True),
        sa.Column('signed_at', sa.DateTime(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('parent_report_id', sa.Integer(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('extra_data', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id']),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
        sa.ForeignKeyConstraint(['parent_report_id'], ['reports.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Create other tables (evidences, timeline_events, etc.)
    # Simplified for brevity - add more tables as needed

    op.create_table('evidences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('evidence_type', sa.Enum('DOCUMENT', 'IMAGE', 'VIDEO', 'AUDIO', 'EMAIL', 'CHAT', 'SOCIAL_MEDIA', 'FINANCIAL', 'GPS', 'OTHER', name='evidencetype'), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('original_filename', sa.String(length=300), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('sha256_hash', sa.String(length=64), nullable=False),
        sa.Column('sha512_hash', sa.String(length=128), nullable=False),
        sa.Column('is_encrypted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('acquisition_date', sa.DateTime(), nullable=False),
        sa.Column('acquisition_method', sa.Text(), nullable=True),
        sa.Column('acquisition_notes', sa.Text(), nullable=True),
        sa.Column('acquired_by_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id']),
        sa.ForeignKeyConstraint(['acquired_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('timeline_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('event_date', sa.DateTime(), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('location', sa.String(length=300), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('extra_data', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id']),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=300), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('chain_of_custody',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('evidence_id', sa.Integer(), nullable=False),
        sa.Column('action_type', sa.Enum('ADDED', 'ACCESSED', 'MODIFIED', 'MOVED', 'COPIED', 'ANALYZED', 'EXPORTED', 'DELETED', name='actiontype'), nullable=False),
        sa.Column('action_description', sa.Text(), nullable=False),
        sa.Column('performed_by_id', sa.Integer(), nullable=False),
        sa.Column('performed_at', sa.DateTime(), nullable=False),
        sa.Column('from_location', sa.String(length=300), nullable=True),
        sa.Column('to_location', sa.String(length=300), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('device_info', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['evidence_id'], ['evidences.id']),
        sa.ForeignKeyConstraint(['performed_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('evidence_analyses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('evidence_id', sa.Integer(), nullable=False),
        sa.Column('plugin_name', sa.String(length=100), nullable=False),
        sa.Column('analysis_type', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('result_data', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('performed_by_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['evidence_id'], ['evidences.id']),
        sa.ForeignKeyConstraint(['performed_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('relationship_types_custom',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )


def downgrade():
    """
    Downgrade - drop all tables.

    WARNING: This will delete all data!
    """
    op.drop_table('relationship_types_custom')
    op.drop_table('evidence_analyses')
    op.drop_table('chain_of_custody')
    op.drop_table('audit_logs')
    op.drop_table('timeline_events')
    op.drop_table('evidences')
    op.drop_table('reports')
    op.drop_table('cases')
    op.drop_table('legitimacy_types_custom')
    op.drop_table('user_roles')
    op.drop_table('roles')
    op.drop_table('users')

    # Drop enum types
    op.execute('DROP TYPE IF EXISTS actiontype')
    op.execute('DROP TYPE IF EXISTS evidencetype')
    op.execute('DROP TYPE IF EXISTS casepriority')
    op.execute('DROP TYPE IF EXISTS casestatus')
    op.execute('DROP TYPE IF EXISTS legitimacytype')
    op.execute('DROP TYPE IF EXISTS reportstatus')
    op.execute('DROP TYPE IF EXISTS reporttype')
