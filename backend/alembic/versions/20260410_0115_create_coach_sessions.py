"""create coach_sessions table

Revision ID: 20260410_0115
Revises: 20260410_0110
Create Date: 2026-04-10 01:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260410_0115'
down_revision: Union[str, None] = '20260410_0110'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'coach_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('target_type', sa.String(50), nullable=False),
        sa.Column('target_id', sa.String(200), nullable=False),
        sa.Column('readiness', sa.String(50), nullable=False),
        sa.Column('active_item_id', sa.String(100), nullable=True),
        sa.Column('completed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_count', sa.Integer(), nullable=False),
        sa.Column('items', postgresql.JSONB(), nullable=False),
        sa.Column('audit_run_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('audit_runs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('target_type', 'target_id', name='uq_coach_session_target'),
    )
    op.create_index('idx_coach_session_readiness', 'coach_sessions', ['readiness'])


def downgrade() -> None:
    op.drop_index('idx_coach_session_readiness', 'coach_sessions')
    op.drop_table('coach_sessions')
