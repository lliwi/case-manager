"""Add monitoring tables for social media surveillance

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-01-17 16:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7c8d9e0f1a2'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create monitoring tables for social media surveillance.

    Tables created:
    - monitoring_tasks: Main monitoring task configuration
    - monitoring_sources: Data sources for monitoring (users, hashtags, searches)
    - monitoring_results: Captured events from monitoring
    - monitoring_check_logs: Audit logs of monitoring executions
    """
    # Check if tables already exist (for idempotency)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # Create monitoring_tasks table
    if 'monitoring_tasks' not in existing_tables:
        op.create_table('monitoring_tasks',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('case_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('monitoring_objective', sa.Text(), nullable=False),
            sa.Column('ai_provider', sa.Enum('DEEPSEEK', 'OPENAI', name='aiprovider'), nullable=False),
            sa.Column('ai_analysis_enabled', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('ai_prompt_template', sa.Text(), nullable=True),
            sa.Column('check_interval_minutes', sa.Integer(), nullable=False, server_default='60'),
            sa.Column('start_date', sa.DateTime(), nullable=False),
            sa.Column('end_date', sa.DateTime(), nullable=True),
            sa.Column('last_check_at', sa.DateTime(), nullable=True),
            sa.Column('next_check_at', sa.DateTime(), nullable=True),
            sa.Column('status', sa.Enum('DRAFT', 'ACTIVE', 'PAUSED', 'COMPLETED', 'ARCHIVED', name='monitoringstatus'), nullable=False, server_default='DRAFT'),
            sa.Column('total_checks', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('total_results', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('alerts_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('unread_alerts_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_by_id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
            sa.Column('deleted_by_id', sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ),
            sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
            sa.ForeignKeyConstraint(['deleted_by_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_monitoring_tasks_case_id'), 'monitoring_tasks', ['case_id'], unique=False)
        op.create_index(op.f('ix_monitoring_tasks_status'), 'monitoring_tasks', ['status'], unique=False)
        op.create_index(op.f('ix_monitoring_tasks_next_check_at'), 'monitoring_tasks', ['next_check_at'], unique=False)
        op.create_index(op.f('ix_monitoring_tasks_is_deleted'), 'monitoring_tasks', ['is_deleted'], unique=False)

    # Create monitoring_sources table
    if 'monitoring_sources' not in existing_tables:
        op.create_table('monitoring_sources',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('task_id', sa.Integer(), nullable=False),
            sa.Column('platform', sa.Enum('X_TWITTER', 'INSTAGRAM', name='sourceplatform'), nullable=False),
            sa.Column('query_type', sa.Enum('USER_PROFILE', 'HASHTAG', 'SEARCH_QUERY', name='sourcequerytype'), nullable=False),
            sa.Column('query_value', sa.String(length=500), nullable=False),
            sa.Column('max_results_per_check', sa.Integer(), nullable=False, server_default='20'),
            sa.Column('include_media', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('last_result_id', sa.String(length=200), nullable=True),
            sa.Column('last_check_at', sa.DateTime(), nullable=True),
            sa.Column('error_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('last_error', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['task_id'], ['monitoring_tasks.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_monitoring_sources_task_id'), 'monitoring_sources', ['task_id'], unique=False)
        op.create_index(op.f('ix_monitoring_sources_is_active'), 'monitoring_sources', ['is_active'], unique=False)

    # Create monitoring_results table
    if 'monitoring_results' not in existing_tables:
        op.create_table('monitoring_results',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('task_id', sa.Integer(), nullable=False),
            sa.Column('source_id', sa.Integer(), nullable=False),
            sa.Column('external_id', sa.String(length=200), nullable=False),
            sa.Column('external_url', sa.String(length=1000), nullable=True),
            sa.Column('content_text', sa.Text(), nullable=True),
            sa.Column('content_metadata', sa.JSON(), nullable=True),
            sa.Column('author_username', sa.String(length=200), nullable=True),
            sa.Column('author_display_name', sa.String(length=300), nullable=True),
            sa.Column('author_profile_url', sa.String(length=500), nullable=True),
            sa.Column('has_media', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('media_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('media_urls', sa.JSON(), nullable=True),
            sa.Column('media_downloaded', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('media_local_paths', sa.JSON(), nullable=True),
            sa.Column('media_hashes', sa.JSON(), nullable=True),
            sa.Column('source_timestamp', sa.DateTime(), nullable=True),
            sa.Column('captured_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('ai_analyzed', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('ai_analysis_timestamp', sa.DateTime(), nullable=True),
            sa.Column('ai_provider_used', sa.String(length=50), nullable=True),
            sa.Column('ai_model_used', sa.String(length=100), nullable=True),
            sa.Column('ai_analysis_result', sa.JSON(), nullable=True),
            sa.Column('ai_relevance_score', sa.Float(), nullable=True),
            sa.Column('ai_summary', sa.Text(), nullable=True),
            sa.Column('ai_flags', sa.JSON(), nullable=True),
            sa.Column('ai_error', sa.Text(), nullable=True),
            sa.Column('is_alert', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('alert_acknowledged', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('alert_acknowledged_by_id', sa.Integer(), nullable=True),
            sa.Column('alert_acknowledged_at', sa.DateTime(), nullable=True),
            sa.Column('alert_notes', sa.Text(), nullable=True),
            sa.Column('saved_as_evidence', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('evidence_id', sa.Integer(), nullable=True),
            sa.Column('content_hash', sa.String(length=64), nullable=False),
            sa.ForeignKeyConstraint(['alert_acknowledged_by_id'], ['users.id'], ),
            sa.ForeignKeyConstraint(['evidence_id'], ['evidences.id'], ),
            sa.ForeignKeyConstraint(['source_id'], ['monitoring_sources.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['task_id'], ['monitoring_tasks.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_monitoring_results_task_id'), 'monitoring_results', ['task_id'], unique=False)
        op.create_index(op.f('ix_monitoring_results_source_id'), 'monitoring_results', ['source_id'], unique=False)
        op.create_index(op.f('ix_monitoring_results_external_id'), 'monitoring_results', ['external_id'], unique=False)
        op.create_index(op.f('ix_monitoring_results_source_timestamp'), 'monitoring_results', ['source_timestamp'], unique=False)
        op.create_index(op.f('ix_monitoring_results_ai_analyzed'), 'monitoring_results', ['ai_analyzed'], unique=False)
        op.create_index(op.f('ix_monitoring_results_is_alert'), 'monitoring_results', ['is_alert'], unique=False)

    # Create monitoring_check_logs table
    if 'monitoring_check_logs' not in existing_tables:
        op.create_table('monitoring_check_logs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('task_id', sa.Integer(), nullable=False),
            sa.Column('check_started_at', sa.DateTime(), nullable=False),
            sa.Column('check_completed_at', sa.DateTime(), nullable=True),
            sa.Column('duration_seconds', sa.Float(), nullable=True),
            sa.Column('sources_checked', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('new_results_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('ai_analyses_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('alerts_generated', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('errors_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('success', sa.Boolean(), nullable=False),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('triggered_by', sa.String(length=50), nullable=False),
            sa.Column('triggered_by_user_id', sa.Integer(), nullable=True),
            sa.Column('celery_task_id', sa.String(length=200), nullable=True),
            sa.ForeignKeyConstraint(['task_id'], ['monitoring_tasks.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['triggered_by_user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_monitoring_check_logs_task_id'), 'monitoring_check_logs', ['task_id'], unique=False)
        op.create_index(op.f('ix_monitoring_check_logs_check_started_at'), 'monitoring_check_logs', ['check_started_at'], unique=False)


def downgrade():
    """Remove monitoring tables."""
    # Drop tables in reverse order due to foreign key constraints
    op.drop_table('monitoring_check_logs')
    op.drop_table('monitoring_results')
    op.drop_table('monitoring_sources')
    op.drop_table('monitoring_tasks')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS monitoringstatus')
    op.execute('DROP TYPE IF EXISTS sourceplatform')
    op.execute('DROP TYPE IF EXISTS sourcequerytype')
    op.execute('DROP TYPE IF EXISTS aiprovider')
