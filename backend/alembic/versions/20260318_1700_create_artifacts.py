"""create investigation_artifacts table

Revision ID: 20260318_1700
Revises: 20260318_1600
Create Date: 2026-03-18 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260318_1700'
down_revision: Union[str, None] = '20260318_1600'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create artifacts table
    op.create_table(
        'investigation_artifacts',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),

        # File information
        sa.Column('file_path', sa.Text(), nullable=False),
        sa.Column('filename', sa.String(500), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),

        # Metadata from filename
        sa.Column('project', sa.String(100), nullable=True),
        sa.Column('artifact_type', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),

        # Content
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),

        # Extracted entities (JSONB arrays)
        sa.Column('jira_keys', postgresql.JSONB(), nullable=True),
        sa.Column('keywords', postgresql.JSONB(), nullable=True),
        sa.Column('entities', postgresql.JSONB(), nullable=True),

        # Timestamps
        sa.Column('file_modified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('indexed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        # Soft delete
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),

        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('file_path')
    )

    # Create indexes for efficient querying
    op.create_index('ix_investigation_artifacts_project', 'investigation_artifacts', ['project'])
    op.create_index('ix_investigation_artifacts_type', 'investigation_artifacts', ['artifact_type'])
    op.create_index('ix_investigation_artifacts_created', 'investigation_artifacts', ['created_at'], postgresql_ops={'created_at': 'DESC'})
    op.create_index('ix_investigation_artifacts_file_path', 'investigation_artifacts', ['file_path'])

    # GIN indexes for JSONB arrays
    op.create_index('ix_investigation_artifacts_jira_keys', 'investigation_artifacts', ['jira_keys'], postgresql_using='gin')
    op.create_index('ix_investigation_artifacts_keywords', 'investigation_artifacts', ['keywords'], postgresql_using='gin')


def downgrade() -> None:
    op.drop_index('ix_investigation_artifacts_keywords', 'investigation_artifacts')
    op.drop_index('ix_investigation_artifacts_jira_keys', 'investigation_artifacts')
    op.drop_index('ix_investigation_artifacts_file_path', 'investigation_artifacts')
    op.drop_index('ix_investigation_artifacts_created', 'investigation_artifacts')
    op.drop_index('ix_investigation_artifacts_type', 'investigation_artifacts')
    op.drop_index('ix_investigation_artifacts_project', 'investigation_artifacts')
    op.drop_table('investigation_artifacts')
