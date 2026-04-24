"""merge multiple heads

Revision ID: 4e9f75d67917
Revises: 20260320_1800, 20260320_2145, 20260320_2220
Create Date: 2026-03-20 17:51:36.096149

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e9f75d67917'
down_revision: Union[str, Sequence[str], None] = ('20260320_1800', '20260320_2145', '20260320_2220')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
