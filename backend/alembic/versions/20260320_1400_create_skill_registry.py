"""create skill registry table

Revision ID: 20260320_1400
Revises: 20260320_1200
Create Date: 2026-03-20 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260320_1400'
down_revision = '20260320_1200'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create skill_registry table
    op.create_table(
        'skill_registry',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('skill_name', sa.String(length=200), nullable=False),
        sa.Column('skill_path', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('trigger_keywords', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('trigger_labels', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('trigger_systems', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('trigger_patterns', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('complexity', sa.String(length=50), nullable=True),
        sa.Column('estimated_duration', sa.String(length=100), nullable=True),
        sa.Column('invocation_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('last_invoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('indexed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('skill_name')
    )

    # Create indexes
    op.create_index('idx_skill_registry_name', 'skill_registry', ['skill_name'])
    op.create_index('idx_skill_registry_category', 'skill_registry', ['category'])
    op.create_index(
        'idx_skill_registry_keywords',
        'skill_registry',
        ['trigger_keywords'],
        postgresql_using='gin'
    )
    op.create_index(
        'idx_skill_registry_labels',
        'skill_registry',
        ['trigger_labels'],
        postgresql_using='gin'
    )


def downgrade() -> None:
    op.drop_table('skill_registry')
