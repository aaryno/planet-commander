"""Create google drive documents table

Revision ID: 20260320_1000
Revises: 20260320_0900
Create Date: 2026-03-20 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260320_1000'
down_revision: Union[str, None] = '20260320_0900'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create google_drive_documents table
    op.create_table(
        'google_drive_documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('external_doc_id', sa.String(length=100), nullable=False),
        sa.Column('doc_type', sa.String(length=50), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('file_path', sa.Text(), nullable=False),
        sa.Column('filename', sa.String(length=500), nullable=True),
        sa.Column('shared_drive', sa.String(length=200), nullable=True),
        sa.Column('folder_path', sa.Text(), nullable=True),
        sa.Column('project', sa.String(length=100), nullable=True),
        sa.Column('document_kind', sa.String(length=100), nullable=True),
        sa.Column('last_modified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('owner', sa.String(length=200), nullable=True),
        sa.Column('jira_keys', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('keywords', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('last_indexed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_doc_id')
    )

    # Create indexes for google_drive_documents
    op.create_index('idx_gdrive_docs_external', 'google_drive_documents', ['external_doc_id'])
    op.create_index('idx_gdrive_docs_shared_drive', 'google_drive_documents', ['shared_drive'])
    op.create_index('idx_gdrive_docs_project', 'google_drive_documents', ['project'])
    op.create_index('idx_gdrive_docs_kind', 'google_drive_documents', ['document_kind'])
    op.create_index('idx_gdrive_docs_modified', 'google_drive_documents', ['last_modified_at'])
    op.create_index('idx_gdrive_docs_jira_keys', 'google_drive_documents', ['jira_keys'], postgresql_using='gin')
    op.create_index('idx_gdrive_docs_keywords', 'google_drive_documents', ['keywords'], postgresql_using='gin')

    # Extend LinkType enum with Google Drive link types
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'documented_in_gdrive'")
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'postmortem_for'")
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'rfd_for'")
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'meeting_notes_for'")


def downgrade() -> None:
    # Drop google_drive_documents table
    op.drop_index('idx_gdrive_docs_keywords', table_name='google_drive_documents', postgresql_using='gin')
    op.drop_index('idx_gdrive_docs_jira_keys', table_name='google_drive_documents', postgresql_using='gin')
    op.drop_index('idx_gdrive_docs_modified', table_name='google_drive_documents')
    op.drop_index('idx_gdrive_docs_kind', table_name='google_drive_documents')
    op.drop_index('idx_gdrive_docs_project', table_name='google_drive_documents')
    op.drop_index('idx_gdrive_docs_shared_drive', table_name='google_drive_documents')
    op.drop_index('idx_gdrive_docs_external', table_name='google_drive_documents')
    op.drop_table('google_drive_documents')

    # Note: Cannot remove enum values in PostgreSQL, they remain but are unused
