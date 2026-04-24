"""create audit_runs table

Revision ID: 20260410_0100
Revises: 20260320_1810
Create Date: 2026-04-10 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260410_0100'
down_revision: Union[str, None] = '20260320_1810'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE auditverdict AS ENUM ('approved', 'changes_required', 'blocked', 'unverified', 'unknown')")
    op.execute("CREATE TYPE auditsource AS ENUM ('deterministic', 'agent_review', 'hybrid')")

    op.create_table(
        'audit_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('audit_family', sa.String(100), nullable=False),
        sa.Column('audit_tier', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('source', postgresql.ENUM('deterministic', 'agent_review', 'hybrid', name='auditsource', create_type=False), nullable=False),
        sa.Column('target_type', sa.String(50), nullable=False),
        sa.Column('target_id', sa.String(200), nullable=False),
        sa.Column('verdict', postgresql.ENUM('approved', 'changes_required', 'blocked', 'unverified', 'unknown', name='auditverdict', create_type=False), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('finding_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('blocking_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('auto_fixable_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('warning_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('dimension_scores', postgresql.JSONB(), nullable=True),
        sa.Column('risk_score', sa.Float(), nullable=True),
        sa.Column('risk_level', sa.String(20), nullable=True),
        sa.Column('risk_factors', postgresql.JSONB(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('model_used', sa.String(100), nullable=True),
        sa.Column('cost_usd', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('raw_output', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_audit_run_family', 'audit_runs', ['audit_family'])
    op.create_index('idx_audit_run_target', 'audit_runs', ['target_type', 'target_id'])
    op.create_index('idx_audit_run_verdict', 'audit_runs', ['verdict'])
    op.create_index('idx_audit_run_created', 'audit_runs', ['created_at'])


def downgrade() -> None:
    op.drop_index('idx_audit_run_created', 'audit_runs')
    op.drop_index('idx_audit_run_verdict', 'audit_runs')
    op.drop_index('idx_audit_run_target', 'audit_runs')
    op.drop_index('idx_audit_run_family', 'audit_runs')
    op.drop_table('audit_runs')
    op.execute("DROP TYPE IF EXISTS auditverdict")
    op.execute("DROP TYPE IF EXISTS auditsource")
