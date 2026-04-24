"""create entity_links table

Revision ID: 20260317_1835
Revises: 20260317_1830
Create Date: 2026-03-17 18:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260317_1835'
down_revision: Union[str, None] = '20260317_1830'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create entity_links table
    # Note: ENUM types are automatically created by SQLAlchemy
    op.create_table(
        'entity_links',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('from_type', sa.String(50), nullable=False),
        sa.Column('from_id', sa.String(200), nullable=False),
        sa.Column('to_type', sa.String(50), nullable=False),
        sa.Column('to_id', sa.String(200), nullable=False),
        sa.Column('link_type', postgresql.ENUM(
            'implements', 'discussed_in', 'references', 'worked_in',
            'checked_out_as', 'summarized_by', 'recommends', 'spawned',
            'derived_from', 'related_to', 'blocked_by', 'follow_up_to',
            'supersedes', 'same_context_as',
            name='linktype'
        ), nullable=False),
        sa.Column('source_type', postgresql.ENUM('manual', 'inferred', 'imported', 'agent', name='linksourcetype'), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('status', postgresql.ENUM('confirmed', 'suggested', 'rejected', 'stale', name='linkstatus'), nullable=False, server_default='confirmed'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for fast lookups
    op.create_index('ix_entity_links_from', 'entity_links', ['from_type', 'from_id'])
    op.create_index('ix_entity_links_to', 'entity_links', ['to_type', 'to_id'])
    op.create_index('ix_entity_links_status', 'entity_links', ['status'])
    op.create_index('ix_entity_links_link_type', 'entity_links', ['link_type'])


def downgrade() -> None:
    op.drop_index('ix_entity_links_link_type', 'entity_links')
    op.drop_index('ix_entity_links_status', 'entity_links')
    op.drop_index('ix_entity_links_to', 'entity_links')
    op.drop_index('ix_entity_links_from', 'entity_links')
    op.drop_table('entity_links')
    # ENUM types are automatically dropped by SQLAlchemy
