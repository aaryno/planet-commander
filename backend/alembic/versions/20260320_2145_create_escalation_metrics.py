"""create warning_escalation_metrics table for learning

Revision ID: 20260320_2145
Revises: 20260320_2100
Create Date: 2026-03-20 21:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260320_2145'
down_revision = '20260320_2100'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create warning_escalation_metrics table
    op.create_table(
        'warning_escalation_metrics',
        sa.Column('alert_name', sa.String(length=200), nullable=False),
        sa.Column('system', sa.String(length=50), nullable=True),
        sa.Column('total_warnings', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('escalated_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('auto_cleared_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('escalation_rate', sa.Float(), nullable=True),
        sa.Column('avg_time_to_escalation_seconds', sa.Integer(), nullable=True),
        sa.Column('avg_time_to_clear_seconds', sa.Integer(), nullable=True),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_escalated', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_calculated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('alert_name')
    )

    # Create indexes
    op.create_index('idx_escalation_metrics_system', 'warning_escalation_metrics', ['system'])
    op.create_index('idx_escalation_metrics_rate', 'warning_escalation_metrics', [sa.text('escalation_rate DESC NULLS LAST')])
    op.create_index('idx_escalation_metrics_last_seen', 'warning_escalation_metrics', ['last_seen'])


def downgrade() -> None:
    op.drop_table('warning_escalation_metrics')
