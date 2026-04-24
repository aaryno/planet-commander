"""create pagerduty_incidents table

Revision ID: 20260318_1500
Revises: 20260318_0305
Create Date: 2026-03-18 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260318_1500'
down_revision: Union[str, None] = '20260318_0305'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create pagerduty_incidents table
    op.create_table(
        'pagerduty_incidents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),

        # External identifiers
        sa.Column('external_incident_id', sa.String(50), nullable=False),
        sa.Column('pd_url', sa.Text(), nullable=True),

        # Incident details
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('urgency', sa.String(50), nullable=True),
        sa.Column('priority', sa.String(50), nullable=True),

        # Service information
        sa.Column('service_id', sa.String(50), nullable=True),
        sa.Column('service_name', sa.String(200), nullable=True),
        sa.Column('escalation_policy_id', sa.String(50), nullable=True),
        sa.Column('escalation_policy_name', sa.String(200), nullable=True),

        # Timeline
        sa.Column('triggered_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_status_change_at', sa.DateTime(timezone=True), nullable=True),

        # Responders (JSONB)
        sa.Column('assigned_to', postgresql.JSONB(), nullable=True),
        sa.Column('acknowledgements', postgresql.JSONB(), nullable=True),

        # Timeline and notes
        sa.Column('incident_timeline', postgresql.JSONB(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),

        # Raw data for audit/debugging
        sa.Column('raw_incident_data', postgresql.JSONB(), nullable=True),

        # Metadata
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        # Soft delete
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),

        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_incident_id')
    )

    # Create indexes
    op.create_index('ix_pagerduty_incidents_external_id', 'pagerduty_incidents', ['external_incident_id'])
    op.create_index('ix_pagerduty_incidents_status', 'pagerduty_incidents', ['status'])
    op.create_index('ix_pagerduty_incidents_triggered', 'pagerduty_incidents', ['triggered_at'])
    op.create_index('ix_pagerduty_incidents_service', 'pagerduty_incidents', ['service_id'])


def downgrade() -> None:
    op.drop_index('ix_pagerduty_incidents_service', 'pagerduty_incidents')
    op.drop_index('ix_pagerduty_incidents_triggered', 'pagerduty_incidents')
    op.drop_index('ix_pagerduty_incidents_status', 'pagerduty_incidents')
    op.drop_index('ix_pagerduty_incidents_external_id', 'pagerduty_incidents')
    op.drop_table('pagerduty_incidents')
