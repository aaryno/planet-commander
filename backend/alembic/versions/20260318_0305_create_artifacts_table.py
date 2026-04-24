"""create artifacts table

Revision ID: 20260318_0305
Revises: 20260318_0302
Create Date: 2026-03-18 03:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260318_0305'
down_revision = '20260318_0302'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'artifacts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('artifact_type', sa.String(50), nullable=False),
        sa.Column('chat_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('context_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('language', sa.String(50), nullable=True),
        sa.Column('message_index', sa.Integer(), nullable=True),
        sa.Column('file_path', sa.String(1000), nullable=True),
        sa.Column('importance', sa.Integer(), nullable=False, default=1),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['chat_id'], ['agents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['context_id'], ['work_contexts.id'], ondelete='SET NULL'),
    )

    # Create indexes
    op.create_index('idx_artifacts_type', 'artifacts', ['artifact_type'])
    op.create_index('idx_artifacts_chat_id', 'artifacts', ['chat_id'])
    op.create_index('idx_artifacts_context_id', 'artifacts', ['context_id'])


def downgrade() -> None:
    op.drop_index('idx_artifacts_context_id', 'artifacts')
    op.drop_index('idx_artifacts_chat_id', 'artifacts')
    op.drop_index('idx_artifacts_type', 'artifacts')
    op.drop_table('artifacts')
