"""add_page_layouts_table

Revision ID: d7e8f9a0b1c2
Revises: b5e7f8c9d0a1
Create Date: 2026-03-16 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd7e8f9a0b1c2'
down_revision: Union[str, Sequence[str], None] = 'b5e7f8c9d0a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'page_layouts',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('page', sa.String(), nullable=False, unique=True),
        sa.Column('layout', postgresql.JSONB(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('page_layouts')
