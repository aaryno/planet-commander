"""add foreign keys to work_contexts

Revision ID: 20260317_1850
Revises: 20260317_1845
Create Date: 2026-03-17 18:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260317_1850'
down_revision: Union[str, None] = '20260317_1845'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add foreign key constraint from work_contexts to jira_issues
    # (had to wait until jira_issues table was created)
    op.create_foreign_key(
        'fk_work_contexts_primary_jira_issue_id',
        'work_contexts',
        'jira_issues',
        ['primary_jira_issue_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_work_contexts_primary_jira_issue_id', 'work_contexts')
