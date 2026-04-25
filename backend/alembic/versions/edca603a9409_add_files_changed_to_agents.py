"""add_files_changed_to_agents

Revision ID: edca603a9409
Revises: b7c4e1a99c16
Create Date: 2026-04-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'edca603a9409'
down_revision: Union[str, Sequence[str], None] = 'b7c4e1a99c16'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('agents', sa.Column('files_changed', postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column('agents', 'files_changed')
