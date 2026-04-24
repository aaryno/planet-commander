"""add diff stat columns to gitlab_merge_requests

Revision ID: 20260410_0110
Revises: 20260410_0105
Create Date: 2026-04-10 01:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260410_0110'
down_revision: Union[str, None] = '20260410_0105'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('gitlab_merge_requests', sa.Column('additions', sa.Integer(), nullable=True))
    op.add_column('gitlab_merge_requests', sa.Column('deletions', sa.Integer(), nullable=True))
    op.add_column('gitlab_merge_requests', sa.Column('changed_file_count', sa.Integer(), nullable=True))
    op.add_column('gitlab_merge_requests', sa.Column('changed_files', postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column('gitlab_merge_requests', 'changed_files')
    op.drop_column('gitlab_merge_requests', 'changed_file_count')
    op.drop_column('gitlab_merge_requests', 'deletions')
    op.drop_column('gitlab_merge_requests', 'additions')
