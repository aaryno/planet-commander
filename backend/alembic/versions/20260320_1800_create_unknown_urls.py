"""create unknown_urls table

Revision ID: 20260320_1800
Revises: 20260320_1405
Create Date: 2026-03-20 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260320_1800'
down_revision: Union[str, None] = '20260320_1405'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'unknown_urls',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('url', sa.String(length=2000), nullable=False),
        sa.Column('domain', sa.String(length=200), nullable=False),
        sa.Column('first_seen_in_chat_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('occurrence_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('reviewed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewed_by', sa.String(length=200), nullable=True),
        sa.Column('promoted_to_pattern', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('promoted_pattern_type', sa.String(length=100), nullable=True),
        sa.Column('ignored', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for common queries
    op.create_index(op.f('ix_unknown_urls_url'), 'unknown_urls', ['url'], unique=False)
    op.create_index(op.f('ix_unknown_urls_domain'), 'unknown_urls', ['domain'], unique=False)
    op.create_index(op.f('ix_unknown_urls_first_seen_in_chat_id'), 'unknown_urls', ['first_seen_in_chat_id'], unique=False)

    # Create foreign key to agents table
    op.create_foreign_key(
        'fk_unknown_urls_chat_id',
        'unknown_urls', 'agents',
        ['first_seen_in_chat_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_unknown_urls_chat_id', 'unknown_urls', type_='foreignkey')
    op.drop_index(op.f('ix_unknown_urls_first_seen_in_chat_id'), table_name='unknown_urls')
    op.drop_index(op.f('ix_unknown_urls_domain'), table_name='unknown_urls')
    op.drop_index(op.f('ix_unknown_urls_url'), table_name='unknown_urls')
    op.drop_table('unknown_urls')
