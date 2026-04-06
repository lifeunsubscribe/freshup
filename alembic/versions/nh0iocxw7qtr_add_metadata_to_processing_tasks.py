"""add_metadata_to_processing_tasks

Revision ID: nh0iocxw7qtr
Revises: 5238c466e2a3
Create Date: 2026-04-06 22:58:47.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'nh0iocxw7qtr'
down_revision: Union[str, None] = '5238c466e2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add task_metadata JSON column to processing_tasks table."""
    with op.batch_alter_table('processing_tasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('task_metadata', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Remove task_metadata column from processing_tasks table."""
    with op.batch_alter_table('processing_tasks', schema=None) as batch_op:
        batch_op.drop_column('task_metadata')
