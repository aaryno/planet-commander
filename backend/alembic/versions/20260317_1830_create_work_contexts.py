"""create work_contexts table

Revision ID: 20260317_1830
Revises: e9f0a1b2c3d4
Create Date: 2026-03-17 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260317_1830'
down_revision: Union[str, None] = 'e9f0a1b2c3d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create work_contexts table
    # Note: ENUM types are automatically created by SQLAlchemy via the ENUM column definitions
    op.create_table(
        'work_contexts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('slug', sa.String(200), nullable=False),
        sa.Column('origin_type', postgresql.ENUM('jira', 'chat', 'branch', 'worktree', 'manual', 'merged', name='origintype'), nullable=False),
        sa.Column('primary_jira_issue_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('primary_chat_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', postgresql.ENUM('active', 'blocked', 'stalled', 'ready', 'done', 'orphaned', 'archived', name='contextstatus'), nullable=False, server_default='active'),
        sa.Column('health_status', postgresql.ENUM('green', 'yellow', 'red', 'unknown', name='healthstatus'), nullable=False, server_default='unknown'),
        sa.Column('summary_text', sa.Text(), nullable=True),
        sa.Column('last_overview_summary_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('last_agent_run_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('owner', sa.String(200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
        sa.ForeignKeyConstraint(['primary_chat_id'], ['agents.id'], ondelete='SET NULL'),
        # Note: Foreign key to jira_issues will be added after that table is created
    )

    # Create indexes
    op.create_index('ix_work_contexts_status', 'work_contexts', ['status'])
    op.create_index('ix_work_contexts_health_status', 'work_contexts', ['health_status'])
    op.create_index('ix_work_contexts_slug', 'work_contexts', ['slug'])


def downgrade() -> None:
    op.drop_index('ix_work_contexts_slug', 'work_contexts')
    op.drop_index('ix_work_contexts_health_status', 'work_contexts')
    op.drop_index('ix_work_contexts_status', 'work_contexts')
    op.drop_table('work_contexts')
    # ENUM types are automatically dropped by SQLAlchemy
