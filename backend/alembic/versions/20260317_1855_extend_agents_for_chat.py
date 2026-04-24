"""extend agents table for chat functionality

Revision ID: 20260317_1855
Revises: 20260317_1850
Create Date: 2026-03-17 18:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260317_1855'
down_revision: Union[str, None] = '20260317_1850'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add Chat-specific fields to agents table
    op.add_column('agents', sa.Column('external_chat_id', sa.String(200), nullable=True))
    op.add_column('agents', sa.Column('workspace_or_source', sa.String(200), nullable=True))
    op.add_column('agents', sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('agents', sa.Column('token_count_estimate', sa.Integer(), nullable=True))
    op.add_column('agents', sa.Column('contains_code', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('agents', sa.Column('contains_ticket_reference', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('agents', sa.Column('contains_worktree_reference', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('agents', sa.Column('generation_index', sa.Integer(), nullable=True))
    op.add_column('agents', sa.Column('parent_chat_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('agents', sa.Column('merged_into_summary_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('agents', sa.Column('context_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('agents', sa.Column('origin_type', sa.String(50), nullable=True))

    # Add foreign key constraints
    op.create_foreign_key('fk_agents_parent_chat_id', 'agents', 'agents', ['parent_chat_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_agents_context_id', 'agents', 'work_contexts', ['context_id'], ['id'], ondelete='SET NULL')

    # Create indexes
    op.create_index('ix_agents_context_id', 'agents', ['context_id'])
    op.create_index('ix_agents_external_chat_id', 'agents', ['external_chat_id'])


def downgrade() -> None:
    op.drop_index('ix_agents_external_chat_id', 'agents')
    op.drop_index('ix_agents_context_id', 'agents')
    op.drop_constraint('fk_agents_context_id', 'agents')
    op.drop_constraint('fk_agents_parent_chat_id', 'agents')
    op.drop_column('agents', 'origin_type')
    op.drop_column('agents', 'context_id')
    op.drop_column('agents', 'merged_into_summary_id')
    op.drop_column('agents', 'parent_chat_id')
    op.drop_column('agents', 'generation_index')
    op.drop_column('agents', 'contains_worktree_reference')
    op.drop_column('agents', 'contains_ticket_reference')
    op.drop_column('agents', 'contains_code')
    op.drop_column('agents', 'token_count_estimate')
    op.drop_column('agents', 'last_message_at')
    op.drop_column('agents', 'workspace_or_source')
    op.drop_column('agents', 'external_chat_id')
