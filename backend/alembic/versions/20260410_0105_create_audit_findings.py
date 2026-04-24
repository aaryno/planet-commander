"""create audit_findings table and extend LinkType enum

Revision ID: 20260410_0105
Revises: 20260410_0100
Create Date: 2026-04-10 01:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260410_0105'
down_revision: Union[str, None] = '20260410_0100'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE findingseverity AS ENUM ('error', 'warning', 'info')")
    op.execute("CREATE TYPE findingcategory AS ENUM ('code-quality', 'security', 'architecture', 'performance', 'adversarial', 'readiness', 'change-risk', 'staleness', 'system', 'context')")
    op.execute("CREATE TYPE findingstatus AS ENUM ('open', 'resolved', 'deferred', 'rejected', 'auto_fixed')")

    op.create_table(
        'audit_findings',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('audit_run_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('audit_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('code', sa.String(100), nullable=False),
        sa.Column('category', postgresql.ENUM(name='findingcategory', create_type=False), nullable=False),
        sa.Column('severity', postgresql.ENUM(name='findingseverity', create_type=False), nullable=False),
        sa.Column('confidence', sa.String(20), nullable=False, server_default='high'),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('blocking', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('auto_fixable', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('actions', postgresql.JSONB(), nullable=True),
        sa.Column('status', postgresql.ENUM(name='findingstatus', create_type=False), nullable=False, server_default=sa.text("'open'")),
        sa.Column('resolution', sa.Text(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', sa.String(100), nullable=True),
        sa.Column('related_entity_type', sa.String(50), nullable=True),
        sa.Column('related_entity_id', sa.String(200), nullable=True),
        sa.Column('source_file', sa.String(500), nullable=True),
        sa.Column('source_line', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_finding_audit_run', 'audit_findings', ['audit_run_id'])
    op.create_index('idx_finding_code', 'audit_findings', ['code'])
    op.create_index('idx_finding_category', 'audit_findings', ['category'])
    op.create_index('idx_finding_severity', 'audit_findings', ['severity'])
    op.create_index('idx_finding_status', 'audit_findings', ['status'])
    op.create_index('idx_finding_entity', 'audit_findings', ['related_entity_type', 'related_entity_id'])

    # Extend LinkType enum with audit values
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'audited_by'")
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'has_finding'")
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'finding_for'")


def downgrade() -> None:
    # Note: PostgreSQL does not support removing values from an enum type.
    # The linktype enum will retain audited_by, has_finding, finding_for values
    # after downgrade. This is safe — unused enum values cause no harm.

    op.drop_index('idx_finding_entity', 'audit_findings')
    op.drop_index('idx_finding_status', 'audit_findings')
    op.drop_index('idx_finding_severity', 'audit_findings')
    op.drop_index('idx_finding_category', 'audit_findings')
    op.drop_index('idx_finding_code', 'audit_findings')
    op.drop_index('idx_finding_audit_run', 'audit_findings')
    op.drop_table('audit_findings')
    op.execute("DROP TYPE IF EXISTS findingstatus")
    op.execute("DROP TYPE IF EXISTS findingcategory")
    op.execute("DROP TYPE IF EXISTS findingseverity")
