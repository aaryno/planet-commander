"""create slack threads table

Revision ID: 20260320_1200
Revises: 20260319_1400
Create Date: 2026-03-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260320_1200'
down_revision = '20260319_1400'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create slack_threads table
    op.create_table(
        'slack_threads',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('channel_id', sa.String(length=50), nullable=False),
        sa.Column('channel_name', sa.String(length=200), nullable=True),
        sa.Column('thread_ts', sa.String(length=50), nullable=False),
        sa.Column('permalink', sa.Text(), nullable=False),
        sa.Column('participant_count', sa.Integer(), nullable=True),
        sa.Column('message_count', sa.Integer(), nullable=True),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_hours', sa.Float(), nullable=True),
        sa.Column('summary_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('summary_text', sa.Text(), nullable=True),
        sa.Column('is_incident', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('severity', sa.String(length=10), nullable=True),
        sa.Column('incident_type', sa.String(length=100), nullable=True),
        sa.Column('surrounding_context_fetched', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('jira_keys', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('pagerduty_incident_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('gitlab_mr_refs', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('cross_channel_refs', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('messages', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('participants', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('reactions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        # Note: Foreign key to summaries table omitted - will be added when summaries table is created
    )

    # Create indexes
    op.create_index('idx_slack_threads_channel', 'slack_threads', ['channel_id'])
    op.create_index(
        'idx_slack_threads_incident',
        'slack_threads',
        ['is_incident'],
        postgresql_where=sa.text('is_incident = TRUE')
    )
    op.create_index('idx_slack_threads_summary', 'slack_threads', ['summary_id'])
    op.create_index('idx_slack_threads_start', 'slack_threads', [sa.text('start_time DESC')])
    op.create_index(
        'idx_slack_threads_jira_keys',
        'slack_threads',
        ['jira_keys'],
        postgresql_using='gin'
    )
    op.create_index(
        'idx_slack_threads_pd_incidents',
        'slack_threads',
        ['pagerduty_incident_ids'],
        postgresql_using='gin'
    )

    # Unique constraint on channel_id + thread_ts
    op.create_unique_constraint('uq_slack_thread', 'slack_threads', ['channel_id', 'thread_ts'])

    # Extend entity_links LinkType enum with Slack thread types
    op.execute("""
        ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'discussed_in_slack';
        ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'references_slack';
        ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'escalated_from';
    """)


def downgrade() -> None:
    op.drop_table('slack_threads')

    # Note: Cannot remove enum values in PostgreSQL without recreating the enum
    # This is acceptable as enum values are harmless if unused
