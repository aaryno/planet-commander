"""create summaries table

Revision ID: 20260318_0302
Revises: 20260317_1855
Create Date: 2026-03-18 03:02:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260318_0302'
down_revision = '20260317_1855'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'summaries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('summary_type', sa.String(50), nullable=False),
        sa.Column('context_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('chat_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('one_liner', sa.String(500), nullable=True),
        sa.Column('short_summary', sa.Text(), nullable=True),
        sa.Column('detailed_summary', sa.Text(), nullable=True),
        sa.Column('model_used', sa.String(100), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=True, default=0),
        sa.Column('input_size', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['context_id'], ['work_contexts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['chat_id'], ['agents.id'], ondelete='CASCADE'),
    )

    # Create indexes
    op.create_index('idx_summaries_type', 'summaries', ['summary_type'])
    op.create_index('idx_summaries_context_id', 'summaries', ['context_id'])
    op.create_index('idx_summaries_chat_id', 'summaries', ['chat_id'])


def downgrade() -> None:
    op.drop_index('idx_summaries_chat_id', 'summaries')
    op.drop_index('idx_summaries_context_id', 'summaries')
    op.drop_index('idx_summaries_type', 'summaries')
    op.drop_table('summaries')
