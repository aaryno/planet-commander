"""create warning_events table for proactive incident response

Revision ID: 20260320_2100
Revises: 20260320_1405
Create Date: 2026-03-20 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260320_2100'
down_revision = '20260320_1405'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create warning_events table
    op.create_table(
        'warning_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('alert_name', sa.String(length=200), nullable=False),
        sa.Column('system', sa.String(length=50), nullable=True),
        sa.Column('channel_id', sa.String(length=50), nullable=False),
        sa.Column('channel_name', sa.String(length=100), nullable=True),
        sa.Column('message_ts', sa.String(length=50), nullable=False),
        sa.Column('thread_ts', sa.String(length=50), nullable=True),
        sa.Column('severity', sa.String(length=10), nullable=False),
        sa.Column('first_seen', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=False),
        sa.Column('escalated', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('escalated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('auto_cleared', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('cleared_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('escalation_probability', sa.Float(), nullable=True),
        sa.Column('escalation_reason', sa.Text(), nullable=True),
        sa.Column('standby_context_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('incident_context_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('raw_message', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for efficient queries
    op.create_index('idx_warning_events_alert_name', 'warning_events', ['alert_name'])
    op.create_index('idx_warning_events_system', 'warning_events', ['system'])
    op.create_index('idx_warning_events_severity', 'warning_events', ['severity'])
    op.create_index('idx_warning_events_first_seen', 'warning_events', ['first_seen'])
    op.create_index('idx_warning_events_escalated', 'warning_events', ['escalated'])

    # Composite index for active warnings query
    op.create_index(
        'idx_warning_events_active',
        'warning_events',
        ['escalated', 'auto_cleared'],
        postgresql_where=sa.text('escalated = false AND auto_cleared = false')
    )


def downgrade() -> None:
    op.drop_table('warning_events')
