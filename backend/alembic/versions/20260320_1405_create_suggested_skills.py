"""create suggested skills table

Revision ID: 20260320_1405
Revises: 20260320_1400
Create Date: 2026-03-20 14:05:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260320_1405'
down_revision = '20260320_1400'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create suggested_skills table
    op.create_table(
        'suggested_skills',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('work_context_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('skill_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('skill_name', sa.String(length=200), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('match_reasons', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('user_action', sa.String(length=50), nullable=True),
        sa.Column('user_feedback', sa.Text(), nullable=True),
        sa.Column('actioned_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('suggested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['work_context_id'], ['work_contexts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['skill_id'], ['skill_registry.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('work_context_id', 'skill_id')
    )

    # Create indexes
    op.create_index('idx_suggested_skills_context', 'suggested_skills', ['work_context_id'])
    op.create_index('idx_suggested_skills_skill', 'suggested_skills', ['skill_id'])
    op.create_index('idx_suggested_skills_confidence', 'suggested_skills', [sa.text('confidence_score DESC')])
    op.create_index('idx_suggested_skills_action', 'suggested_skills', ['user_action'])


def downgrade() -> None:
    op.drop_table('suggested_skills')
