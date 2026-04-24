"""add_mr_review_table

Revision ID: b5e7f8c9d0a1
Revises: a3f1b2c4d5e6
Create Date: 2026-03-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b5e7f8c9d0a1'
down_revision: Union[str, Sequence[str], None] = 'a3f1b2c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'mr_reviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project', sa.String(), nullable=False),
        sa.Column('mr_iid', sa.Integer(), nullable=False),
        sa.Column('last_commit_sha', sa.String(), nullable=True),
        sa.Column('needs_review', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('reviews', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_mr_reviews_project'), 'mr_reviews', ['project'], unique=False)
    op.create_index(op.f('ix_mr_reviews_mr_iid'), 'mr_reviews', ['mr_iid'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_mr_reviews_mr_iid'), table_name='mr_reviews')
    op.drop_index(op.f('ix_mr_reviews_project'), table_name='mr_reviews')
    op.drop_table('mr_reviews')
