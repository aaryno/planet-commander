"""Create project docs tables

Revision ID: 20260320_0900
Revises: 20260319_0900
Create Date: 2026-03-20 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260320_0900'
down_revision: Union[str, None] = '20260319_0900'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create project_docs table
    op.create_table(
        'project_docs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_name', sa.String(length=100), nullable=False),
        sa.Column('file_path', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('sections', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('keywords', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('links', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('team', sa.String(length=100), nullable=True),
        sa.Column('primary_contact', sa.String(length=200), nullable=True),
        sa.Column('repositories', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('slack_channels', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('file_modified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_name')
    )

    # Create indexes for project_docs
    op.create_index('idx_project_docs_name', 'project_docs', ['project_name'])
    op.create_index('idx_project_docs_team', 'project_docs', ['team'])
    op.create_index('idx_project_docs_modified', 'project_docs', ['file_modified_at'])
    op.create_index('idx_project_docs_keywords', 'project_docs', ['keywords'], postgresql_using='gin')

    # Create project_doc_sections table
    op.create_table(
        'project_doc_sections',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_doc_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('section_name', sa.String(length=200), nullable=False),
        sa.Column('heading_level', sa.Integer(), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_doc_id'], ['project_docs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for project_doc_sections
    op.create_index('idx_doc_sections_project', 'project_doc_sections', ['project_doc_id'])
    op.create_index('idx_doc_sections_name', 'project_doc_sections', ['section_name'])
    op.create_index('idx_doc_sections_order', 'project_doc_sections', ['project_doc_id', 'order_index'], unique=True)

    # Extend LinkType enum with new project doc link types
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'project_context'")
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'documented_in'")
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'references_project'")


def downgrade() -> None:
    # Drop project_doc_sections table
    op.drop_index('idx_doc_sections_order', table_name='project_doc_sections')
    op.drop_index('idx_doc_sections_name', table_name='project_doc_sections')
    op.drop_index('idx_doc_sections_project', table_name='project_doc_sections')
    op.drop_table('project_doc_sections')

    # Drop project_docs table
    op.drop_index('idx_project_docs_keywords', table_name='project_docs', postgresql_using='gin')
    op.drop_index('idx_project_docs_modified', table_name='project_docs')
    op.drop_index('idx_project_docs_team', table_name='project_docs')
    op.drop_index('idx_project_docs_name', table_name='project_docs')
    op.drop_table('project_docs')

    # Note: Cannot remove enum values in PostgreSQL, they remain but are unused
