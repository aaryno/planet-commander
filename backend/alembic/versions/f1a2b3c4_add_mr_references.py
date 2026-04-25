"""add_mr_references_to_agents

Revision ID: f1a2b3c4
Revises: edca603a9409
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'f1a2b3c4'
down_revision: Union[str, Sequence[str], None] = 'edca603a9409'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('agents', sa.Column('mr_references', postgresql.JSONB(), nullable=True))

def downgrade() -> None:
    op.drop_column('agents', 'mr_references')
