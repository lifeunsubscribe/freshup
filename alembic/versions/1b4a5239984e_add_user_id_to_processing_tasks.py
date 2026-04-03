"""add user_id to processing_tasks

Revision ID: 1b4a5239984e
Revises: ic6ciyat2lmp
Create Date: 2026-03-29 14:18:56.310634

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1b4a5239984e'
down_revision: Union[str, None] = 'ic6ciyat2lmp'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add user_id column to processing_tasks table."""
    with op.batch_alter_table('processing_tasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.UUID(), nullable=False))
        batch_op.create_foreign_key(
            'fk_processing_tasks_user_id_users',
            'users',
            ['user_id'],
            ['id']
        )


def downgrade() -> None:
    """Remove user_id column from processing_tasks table."""
    with op.batch_alter_table('processing_tasks', schema=None) as batch_op:
        batch_op.drop_constraint('fk_processing_tasks_user_id_users', type_='foreignkey')
        batch_op.drop_column('user_id')
