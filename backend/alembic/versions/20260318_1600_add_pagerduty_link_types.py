"""add pagerduty link types to enum

Revision ID: 20260318_1600
Revises: 20260318_1500
Create Date: 2026-03-18 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260318_1600'
down_revision: Union[str, None] = '20260318_1500'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new enum values for PagerDuty link types
    # PostgreSQL requires explicit enum extension
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'references_pagerduty'")
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'discussed_in_pagerduty'")


def downgrade() -> None:
    # Cannot remove enum values in PostgreSQL without recreating the enum
    # This is a one-way migration
    pass
