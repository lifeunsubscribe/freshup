"""add index to processing_tasks user_id

Revision ID: ke8flacv4noq
Revises: 1b4a5239984e
Create Date: 2026-04-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ke8flacv4noq'
down_revision: Union[str, None] = '1b4a5239984e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add index to processing_tasks.user_id for query optimization.

    While the current task status endpoint (GET /tasks/{task_id}) queries by
    primary key first, this index provides:
    - Performance optimization for foreign key constraints
    - Future support for user-specific task listing (GET /users/{user_id}/tasks)
    - Query planner hints for multi-tenant isolation checks

    This is a standard best practice for foreign key columns in multi-tenant
    systems to ensure efficient data access patterns as the application scales.
    """
    with op.batch_alter_table('processing_tasks', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_processing_tasks_user_id'),
            ['user_id'],
            unique=False
        )


def downgrade() -> None:
    """Remove index from processing_tasks.user_id."""
    with op.batch_alter_table('processing_tasks', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_processing_tasks_user_id'))
