"""Create gitlab merge requests table

Revision ID: 20260320_1100
Revises: 20260320_1000
Create Date: 2026-03-20 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260320_1100'
down_revision: Union[str, None] = '20260320_1000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create gitlab_merge_requests table
    op.create_table(
        'gitlab_merge_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),

        # GitLab identity
        sa.Column('external_mr_id', sa.Integer(), nullable=False),
        sa.Column('repository', sa.String(length=200), nullable=False),

        # MR metadata
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('url', sa.Text(), nullable=False),

        # Branches
        sa.Column('source_branch', sa.String(length=200), nullable=False),
        sa.Column('target_branch', sa.String(length=200), nullable=False),

        # People
        sa.Column('author', sa.String(length=200), nullable=False),
        sa.Column('reviewers', postgresql.JSONB(astext_type=sa.Text()), nullable=True),

        # Status
        sa.Column('approval_status', sa.String(length=50), nullable=True),
        sa.Column('ci_status', sa.String(length=50), nullable=True),
        sa.Column('state', sa.String(length=50), nullable=False),

        # Extracted metadata
        sa.Column('jira_keys', postgresql.ARRAY(sa.Text()), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('merged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('repository', 'external_mr_id', name='uq_gitlab_mr_repo_id')
    )

    # Create indexes
    op.create_index('idx_gitlab_mr_repo', 'gitlab_merge_requests', ['repository'])
    op.create_index('idx_gitlab_mr_state', 'gitlab_merge_requests', ['state'])
    op.create_index('idx_gitlab_mr_source_branch', 'gitlab_merge_requests', ['source_branch'])
    op.create_index('idx_gitlab_mr_author', 'gitlab_merge_requests', ['author'])
    op.create_index('idx_gitlab_mr_jira_keys', 'gitlab_merge_requests', ['jira_keys'], postgresql_using='gin')
    op.create_index('idx_gitlab_mr_created', 'gitlab_merge_requests', ['created_at'])

    # Extend LinkType enum with GitLab MR link types
    # Note: 'implements' already exists, only add new ones
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'implemented_by'")
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'reviewed_in'")
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'merged_to_branch'")


def downgrade() -> None:
    # Drop gitlab_merge_requests table
    op.drop_index('idx_gitlab_mr_created', table_name='gitlab_merge_requests')
    op.drop_index('idx_gitlab_mr_jira_keys', table_name='gitlab_merge_requests', postgresql_using='gin')
    op.drop_index('idx_gitlab_mr_author', table_name='gitlab_merge_requests')
    op.drop_index('idx_gitlab_mr_source_branch', table_name='gitlab_merge_requests')
    op.drop_index('idx_gitlab_mr_state', table_name='gitlab_merge_requests')
    op.drop_index('idx_gitlab_mr_repo', table_name='gitlab_merge_requests')
    op.drop_table('gitlab_merge_requests')

    # Note: Cannot remove enum values in PostgreSQL, they remain but are unused
