"""create warning feedback table

Revision ID: 20260320_2220
Revises: (previous revision)
Create Date: 2026-03-20 22:20:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260320_2220'
down_revision = None  # TODO: Update with actual previous revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create feedback_type enum
    feedback_type_enum = postgresql.ENUM(
        'prediction_accuracy',
        'context_usefulness',
        'escalation_timing',
        name='feedbacktype',
        create_type=True
    )
    feedback_type_enum.create(op.get_bind(), checkfirst=True)

    # Create warning_feedback table
    op.create_table(
        'warning_feedback',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('warning_event_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('feedback_type', feedback_type_enum, nullable=False),

        # Prediction accuracy feedback
        sa.Column('prediction_was_correct', sa.Boolean(), nullable=True),
        sa.Column('actual_escalated', sa.Boolean(), nullable=True),
        sa.Column('predicted_probability', sa.Float(), nullable=True),

        # Context usefulness feedback
        sa.Column('context_was_useful', sa.Boolean(), nullable=True),
        sa.Column('missing_information', sa.Text(), nullable=True),

        # Escalation timing feedback (future)
        sa.Column('escalation_timing_accurate', sa.Boolean(), nullable=True),
        sa.Column('actual_escalation_time', sa.DateTime(timezone=True), nullable=True),

        # User info
        sa.Column('submitted_by', sa.String(200), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        # Optional comment
        sa.Column('comment', sa.Text(), nullable=True),

        # Foreign key
        sa.ForeignKeyConstraint(['warning_event_id'], ['warning_events.id'], ondelete='CASCADE'),
    )

    # Create indexes
    op.create_index('idx_warning_feedback_event', 'warning_feedback', ['warning_event_id'])
    op.create_index('idx_warning_feedback_type', 'warning_feedback', ['feedback_type'])
    op.create_index('idx_warning_feedback_submitted', 'warning_feedback', ['submitted_at'])


def downgrade() -> None:
    op.drop_index('idx_warning_feedback_submitted', 'warning_feedback')
    op.drop_index('idx_warning_feedback_type', 'warning_feedback')
    op.drop_index('idx_warning_feedback_event', 'warning_feedback')
    op.drop_table('warning_feedback')

    # Drop enum
    feedback_type_enum = postgresql.ENUM(
        'prediction_accuracy',
        'context_usefulness',
        'escalation_timing',
        name='feedbacktype'
    )
    feedback_type_enum.drop(op.get_bind(), checkfirst=True)
