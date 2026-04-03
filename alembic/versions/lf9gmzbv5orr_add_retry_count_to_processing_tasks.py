"""add retry_count to processing_tasks

Revision ID: lf9gmzbv5orr
Revises: ke8flacv4noq
Create Date: 2026-04-03 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'lf9gmzbv5orr'
down_revision: Union[str, None] = 'ke8flacv4noq'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add retry_count field to track stale task recovery attempts.

    This field tracks how many times a task has been recovered from stale
    "processing" status, preventing infinite retry loops for tasks that
    consistently crash workers. When retry_count exceeds the configured
    task_max_retry_count, the task is marked as failed instead of being
    retried.
    """
    with op.batch_alter_table('processing_tasks', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0')
        )


def downgrade() -> None:
    """Remove retry_count field."""
    with op.batch_alter_table('processing_tasks', schema=None) as batch_op:
        batch_op.drop_column('retry_count')
