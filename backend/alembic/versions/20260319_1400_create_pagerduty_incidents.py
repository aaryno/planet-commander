"""create pagerduty incidents table

Revision ID: 20260319_1400
Revises: 20260320_1100
Create Date: 2026-03-19 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260319_1400'
down_revision = '20260320_1100'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create pagerduty_incidents table
    op.create_table(
        'pagerduty_incidents',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('external_incident_id', sa.String(length=50), nullable=False),
        sa.Column('incident_number', sa.Integer(), nullable=True),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('urgency', sa.String(length=20), nullable=True),
        sa.Column('priority', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('service_id', sa.String(length=50), nullable=True),
        sa.Column('service_name', sa.String(length=200), nullable=True),
        sa.Column('escalation_policy_id', sa.String(length=50), nullable=True),
        sa.Column('escalation_policy_name', sa.String(length=200), nullable=True),
        sa.Column('assigned_to', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('teams', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('triggered_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_status_change_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('incident_url', sa.Text(), nullable=True),
        sa.Column('html_url', sa.Text(), nullable=True),
        sa.Column('incident_key', sa.String(length=200), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('acknowledgements', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('assignments', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('log_entries', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('alerts', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('idx_pd_incidents_external', 'pagerduty_incidents', ['external_incident_id'])
    op.create_index('idx_pd_incidents_number', 'pagerduty_incidents', ['incident_number'])
    op.create_index('idx_pd_incidents_status', 'pagerduty_incidents', ['status'])
    op.create_index('idx_pd_incidents_urgency', 'pagerduty_incidents', ['urgency'])
    op.create_index('idx_pd_incidents_service', 'pagerduty_incidents', ['service_id'])
    op.create_index('idx_pd_incidents_triggered', 'pagerduty_incidents', [sa.text('triggered_at DESC')])
    op.create_index(
        'idx_pd_incidents_resolved',
        'pagerduty_incidents',
        ['resolved_at'],
        postgresql_where=sa.text('resolved_at IS NOT NULL')
    )
    op.create_index(
        'idx_pd_incidents_team',
        'pagerduty_incidents',
        ['teams'],
        postgresql_using='gin'
    )

    # Unique constraint on external_incident_id
    op.create_unique_constraint('uq_pd_incident_external', 'pagerduty_incidents', ['external_incident_id'])

    # Extend entity_links LinkType enum with PagerDuty types
    op.execute("""
        ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'triggered_by';
        ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'escalated_to';
        ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'discussed_in';
        ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'incident_for';
    """)


def downgrade() -> None:
    op.drop_table('pagerduty_incidents')

    # Note: Cannot remove enum values in PostgreSQL without recreating the enum
    # This is acceptable as enum values are harmless if unused
