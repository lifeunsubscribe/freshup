"""add processing_started_at to processing_tasks

Revision ID: jd7ekzbu3mnq
Revises: ic6ciyat2lmp
Create Date: 2026-03-31 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'jd7ekzbu3mnq'
down_revision: Union[str, None] = 'ic6ciyat2lmp'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add processing_started_at timestamp to track task processing start time.

    This field is used to detect stale tasks stuck in "processing" status
    due to worker crashes, enabling automatic recovery.
    """
    # Add processing_started_at column
    with op.batch_alter_table('processing_tasks', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('processing_started_at', sa.DateTime(), nullable=True)
        )

        # Add index for efficient stale task detection queries
        batch_op.create_index(
            'ix_processing_tasks_status_processing_started_at',
            ['status', 'processing_started_at'],
            unique=False
        )


def downgrade() -> None:
    """Remove processing_started_at field and its index."""
    with op.batch_alter_table('processing_tasks', schema=None) as batch_op:
        batch_op.drop_index('ix_processing_tasks_status_processing_started_at')
        batch_op.drop_column('processing_started_at')
