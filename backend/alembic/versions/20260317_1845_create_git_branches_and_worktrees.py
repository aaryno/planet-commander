"""create git_branches and worktrees tables

Revision ID: 20260317_1845
Revises: 20260317_1840
Create Date: 2026-03-17 18:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260317_1845'
down_revision: Union[str, None] = '20260317_1840'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create git_branches table
    # Note: ENUM types are automatically created by SQLAlchemy
    op.create_table(
        'git_branches',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('repo', sa.String(200), nullable=False),
        sa.Column('branch_name', sa.String(200), nullable=False),
        sa.Column('head_sha', sa.String(40), nullable=False),
        sa.Column('base_branch', sa.String(200), nullable=False),
        sa.Column('status', postgresql.ENUM('active', 'merged', 'stale', 'abandoned', name='branchstatus'), nullable=False, server_default='active'),
        sa.Column('ahead_count', sa.Integer(), nullable=True),
        sa.Column('behind_count', sa.Integer(), nullable=True),
        sa.Column('has_open_pr', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('pr_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('context_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('linked_ticket_key_guess', sa.String(50), nullable=True),
        sa.Column('is_inferred', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['context_id'], ['work_contexts.id'], ondelete='SET NULL')
    )

    # Create indexes for git_branches
    op.create_index('ix_git_branches_repo', 'git_branches', ['repo'])
    op.create_index('ix_git_branches_branch_name', 'git_branches', ['branch_name'])
    op.create_index('ix_git_branches_status', 'git_branches', ['status'])
    op.create_index('ix_git_branches_context_id', 'git_branches', ['context_id'])

    # Create worktrees table
    op.create_table(
        'worktrees',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('repo', sa.String(200), nullable=False),
        sa.Column('path', sa.String(500), nullable=False),
        sa.Column('branch_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', postgresql.ENUM('active', 'dirty', 'clean', 'stale', 'merged', 'abandoned', 'orphaned', name='worktreestatus'), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('has_uncommitted_changes', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('has_untracked_files', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_rebasing', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_out_of_date', sa.Boolean(), nullable=False, server_default='false'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('path'),
        sa.ForeignKeyConstraint(['branch_id'], ['git_branches.id'], ondelete='CASCADE')
    )

    # Create indexes for worktrees
    op.create_index('ix_worktrees_repo', 'worktrees', ['repo'])
    op.create_index('ix_worktrees_path', 'worktrees', ['path'])
    op.create_index('ix_worktrees_branch_id', 'worktrees', ['branch_id'])
    op.create_index('ix_worktrees_status', 'worktrees', ['status'])
    op.create_index('ix_worktrees_is_active', 'worktrees', ['is_active'])


def downgrade() -> None:
    op.drop_index('ix_worktrees_is_active', 'worktrees')
    op.drop_index('ix_worktrees_status', 'worktrees')
    op.drop_index('ix_worktrees_branch_id', 'worktrees')
    op.drop_index('ix_worktrees_path', 'worktrees')
    op.drop_index('ix_worktrees_repo', 'worktrees')
    op.drop_table('worktrees')

    op.drop_index('ix_git_branches_context_id', 'git_branches')
    op.drop_index('ix_git_branches_status', 'git_branches')
    op.drop_index('ix_git_branches_branch_name', 'git_branches')
    op.drop_index('ix_git_branches_repo', 'git_branches')
    op.drop_table('git_branches')

    # ENUM types are automatically dropped by SQLAlchemy
