"""add metadata to entity_links

Revision ID: 20260320_1810
Revises: 4e9f75d67917
Create Date: 2026-03-20 18:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260320_1810'
down_revision: Union[str, None] = '4e9f75d67917'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add link_metadata column to entity_links
    op.add_column('entity_links', sa.Column('link_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('entity_links', 'link_metadata')
