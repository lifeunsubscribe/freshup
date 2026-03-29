"""add processing tasks table

Revision ID: ic6ciyat2lmp
Revises: f9d8c7b6a5e4
Create Date: 2026-03-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ic6ciyat2lmp'
down_revision: Union[str, None] = 'f9d8c7b6a5e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create processing_tasks table for tracking async LLM processing jobs."""
    op.create_table(
        'processing_tasks',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('task_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('input_reference', sa.Text(), nullable=False),
        sa.Column('result_reference', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create compound index for efficient pending task queries
    with op.batch_alter_table('processing_tasks', schema=None) as batch_op:
        batch_op.create_index(
            'ix_processing_tasks_status_created_at',
            ['status', 'created_at'],
            unique=False
        )


def downgrade() -> None:
    """Drop processing_tasks table and its indexes."""
    with op.batch_alter_table('processing_tasks', schema=None) as batch_op:
        batch_op.drop_index('ix_processing_tasks_status_created_at')

    op.drop_table('processing_tasks')
