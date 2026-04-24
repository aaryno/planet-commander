"""add workspace tables

Revision ID: e9f0a1b2c3d4
Revises: d7e8f9a0b1c2
Create Date: 2026-03-17 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e9f0a1b2c3d4'
down_revision: Union[str, None] = '218d38542662'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create workspaces table
    op.create_table(
        'workspaces',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('project', sa.String(length=50), nullable=False),
        sa.Column('created_from_type', sa.String(length=20), nullable=False),
        sa.Column('created_from_id', sa.String(length=200), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_active_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_workspaces_project', 'workspaces', ['project'])
    op.create_index('ix_workspaces_last_active_at', 'workspaces', ['last_active_at'])

    # Create workspace_jira_tickets table
    op.create_table(
        'workspace_jira_tickets',
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('jira_key', sa.String(length=50), nullable=False),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('description_expanded', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('comments_expanded', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('pinned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('workspace_id', 'jira_key')
    )
    op.create_index('ix_workspace_jira_tickets_workspace_id', 'workspace_jira_tickets', ['workspace_id'])
    op.create_index('ix_workspace_jira_tickets_jira_key', 'workspace_jira_tickets', ['jira_key'])

    # Create workspace_agents table
    op.create_table(
        'workspace_agents',
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('is_pinned', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('workspace_id', 'agent_id')
    )
    op.create_index('ix_workspace_agents_workspace_id', 'workspace_agents', ['workspace_id'])
    op.create_index('ix_workspace_agents_agent_id', 'workspace_agents', ['agent_id'])

    # Create workspace_agent_jira table
    op.create_table(
        'workspace_agent_jira',
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('jira_key', sa.String(length=50), nullable=False),
        sa.Column('linked_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(
            ['workspace_id', 'agent_id'],
            ['workspace_agents.workspace_id', 'workspace_agents.agent_id'],
            ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['workspace_id', 'jira_key'],
            ['workspace_jira_tickets.workspace_id', 'workspace_jira_tickets.jira_key'],
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('workspace_id', 'agent_id', 'jira_key')
    )

    # Create workspace_branches table
    op.create_table(
        'workspace_branches',
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('branch_name', sa.String(length=200), nullable=False),
        sa.Column('worktree_path', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('workspace_id', 'branch_name')
    )
    op.create_index('ix_workspace_branches_workspace_id', 'workspace_branches', ['workspace_id'])

    # Create workspace_branch_jira table
    op.create_table(
        'workspace_branch_jira',
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('branch_name', sa.String(length=200), nullable=False),
        sa.Column('jira_key', sa.String(length=50), nullable=False),
        sa.Column('linked_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(
            ['workspace_id', 'branch_name'],
            ['workspace_branches.workspace_id', 'workspace_branches.branch_name'],
            ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['workspace_id', 'jira_key'],
            ['workspace_jira_tickets.workspace_id', 'workspace_jira_tickets.jira_key'],
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('workspace_id', 'branch_name', 'jira_key')
    )

    # Create workspace_mrs table
    op.create_table(
        'workspace_mrs',
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('mr_project', sa.String(length=100), nullable=False),
        sa.Column('mr_iid', sa.Integer(), nullable=False),
        sa.Column('branch_name', sa.String(length=200), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('url', sa.String(length=500), nullable=True),
        sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('workspace_id', 'mr_project', 'mr_iid')
    )
    op.create_index('ix_workspace_mrs_workspace_id', 'workspace_mrs', ['workspace_id'])

    # Create workspace_deployments table
    op.create_table(
        'workspace_deployments',
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('environment', sa.String(length=100), nullable=False),
        sa.Column('namespace', sa.String(length=100), nullable=False, server_default=''),
        sa.Column('version', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('url', sa.String(length=500), nullable=True),
        sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('workspace_id', 'environment', 'namespace')
    )
    op.create_index('ix_workspace_deployments_workspace_id', 'workspace_deployments', ['workspace_id'])


def downgrade() -> None:
    # Drop tables in reverse order (respecting foreign key constraints)
    op.drop_index('ix_workspace_deployments_workspace_id', table_name='workspace_deployments')
    op.drop_table('workspace_deployments')

    op.drop_index('ix_workspace_mrs_workspace_id', table_name='workspace_mrs')
    op.drop_table('workspace_mrs')

    op.drop_table('workspace_branch_jira')

    op.drop_index('ix_workspace_branches_workspace_id', table_name='workspace_branches')
    op.drop_table('workspace_branches')

    op.drop_table('workspace_agent_jira')

    op.drop_index('ix_workspace_agents_agent_id', table_name='workspace_agents')
    op.drop_index('ix_workspace_agents_workspace_id', table_name='workspace_agents')
    op.drop_table('workspace_agents')

    op.drop_index('ix_workspace_jira_tickets_jira_key', table_name='workspace_jira_tickets')
    op.drop_index('ix_workspace_jira_tickets_workspace_id', table_name='workspace_jira_tickets')
    op.drop_table('workspace_jira_tickets')

    op.drop_index('ix_workspaces_last_active_at', table_name='workspaces')
    op.drop_index('ix_workspaces_project', table_name='workspaces')
    op.drop_table('workspaces')
