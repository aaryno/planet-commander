"""create jira_issues table

Revision ID: 20260317_1840
Revises: 20260317_1835
Create Date: 2026-03-17 18:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260317_1840'
down_revision: Union[str, None] = '20260317_1835'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create jira_issues table
    op.create_table(
        'jira_issues',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('external_key', sa.String(50), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('status', sa.String(100), nullable=False),
        sa.Column('priority', sa.String(50), nullable=True),
        sa.Column('assignee', sa.String(200), nullable=True),
        sa.Column('labels', postgresql.JSONB(), nullable=True),
        sa.Column('fix_versions', postgresql.JSONB(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('acceptance_criteria', sa.Text(), nullable=True),
        sa.Column('url', sa.String(500), nullable=False),
        sa.Column('source_last_synced_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('agent_ready', sa.Boolean(), nullable=True),
        sa.Column('context_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('last_context_audit_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('last_acceptance_audit_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_key'),
        sa.ForeignKeyConstraint(['context_id'], ['work_contexts.id'], ondelete='SET NULL')
    )

    # Create indexes
    op.create_index('ix_jira_issues_external_key', 'jira_issues', ['external_key'])
    op.create_index('ix_jira_issues_status', 'jira_issues', ['status'])
    op.create_index('ix_jira_issues_context_id', 'jira_issues', ['context_id'])


def downgrade() -> None:
    op.drop_index('ix_jira_issues_context_id', 'jira_issues')
    op.drop_index('ix_jira_issues_status', 'jira_issues')
    op.drop_index('ix_jira_issues_external_key', 'jira_issues')
    op.drop_table('jira_issues')
