"""Create grafana alert definitions tables

Revision ID: 20260319_0900
Revises: 20260318_0305
Create Date: 2026-03-19 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260319_0900'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create grafana_alert_definitions table
    op.create_table(
        'grafana_alert_definitions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.func.gen_random_uuid(), nullable=False),
        sa.Column('alert_name', sa.String(200), nullable=False),
        sa.Column('file_path', sa.Text(), nullable=False),
        sa.Column('team', sa.String(100), nullable=True),
        sa.Column('project', sa.String(100), nullable=True),
        sa.Column('alert_expr', sa.Text(), nullable=False),
        sa.Column('alert_for', sa.String(50), nullable=True),
        sa.Column('labels', postgresql.JSONB, nullable=True),
        sa.Column('annotations', postgresql.JSONB, nullable=True),
        sa.Column('severity', sa.String(10), nullable=True),
        sa.Column('runbook_url', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('file_modified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('alert_name')
    )

    # Create indexes for grafana_alert_definitions
    op.create_index('ix_alert_defs_name', 'grafana_alert_definitions', ['alert_name'])
    op.create_index('ix_alert_defs_team', 'grafana_alert_definitions', ['team'])
    op.create_index('ix_alert_defs_project', 'grafana_alert_definitions', ['project'])
    op.create_index('ix_alert_defs_severity', 'grafana_alert_definitions', ['severity'])
    op.create_index('ix_alert_defs_labels', 'grafana_alert_definitions', ['labels'], postgresql_using='gin')

    # Create grafana_alert_firings table
    op.create_table(
        'grafana_alert_firings',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.func.gen_random_uuid(), nullable=False),
        sa.Column('alert_definition_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('alert_name', sa.String(200), nullable=False),
        sa.Column('fired_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('state', sa.String(50), nullable=True),
        sa.Column('labels', postgresql.JSONB, nullable=True),
        sa.Column('annotations', postgresql.JSONB, nullable=True),
        sa.Column('fingerprint', sa.String(100), nullable=True),
        sa.Column('value', sa.Float(), nullable=True),
        sa.Column('external_alert_id', sa.String(100), nullable=True),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['alert_definition_id'], ['grafana_alert_definitions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for grafana_alert_firings
    op.create_index('ix_alert_firings_def', 'grafana_alert_firings', ['alert_definition_id'])
    op.create_index('ix_alert_firings_name', 'grafana_alert_firings', ['alert_name'])
    op.create_index('ix_alert_firings_fired', 'grafana_alert_firings', ['fired_at'], postgresql_ops={'fired_at': 'DESC'})
    op.create_index('ix_alert_firings_state', 'grafana_alert_firings', ['state'])
    op.create_index('ix_alert_firings_fingerprint', 'grafana_alert_firings', ['fingerprint'])

    # Add new link types to LinkType enum
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'triggered_alert'")
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'discussed_alert'")
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'references_alert'")


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_alert_firings_fingerprint', table_name='grafana_alert_firings')
    op.drop_index('ix_alert_firings_state', table_name='grafana_alert_firings')
    op.drop_index('ix_alert_firings_fired', table_name='grafana_alert_firings')
    op.drop_index('ix_alert_firings_name', table_name='grafana_alert_firings')
    op.drop_index('ix_alert_firings_def', table_name='grafana_alert_firings')

    op.drop_index('ix_alert_defs_labels', table_name='grafana_alert_definitions')
    op.drop_index('ix_alert_defs_severity', table_name='grafana_alert_definitions')
    op.drop_index('ix_alert_defs_project', table_name='grafana_alert_definitions')
    op.drop_index('ix_alert_defs_team', table_name='grafana_alert_definitions')
    op.drop_index('ix_alert_defs_name', table_name='grafana_alert_definitions')

    # Drop tables
    op.drop_table('grafana_alert_firings')
    op.drop_table('grafana_alert_definitions')

    # Note: Cannot remove enum values in PostgreSQL, they persist
