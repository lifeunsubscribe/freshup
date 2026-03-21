"""add_created_at_to_grocery_list_items

Adds created_at timestamp column to grocery_list_items table to enable
proper chronological ordering. Previously, items were ordered by UUID
(id field), which doesn't guarantee chronological order and can produce
incorrect ordering in bulk imports, migrations, and concurrent operations.

The created_at field uses server_default=CURRENT_TIMESTAMP to ensure
existing rows are backfilled with the migration timestamp.

An index is added on created_at to optimize ORDER BY queries.

Revision ID: a1b2c3d4e5f6
Revises: f9d8c7b6a5e4
Create Date: 2026-03-21 17:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f9d8c7b6a5e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add created_at column to grocery_list_items table
    # Use server_default to populate existing rows with migration timestamp
    with op.batch_alter_table('grocery_list_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False))
        batch_op.create_index('ix_grocery_list_items_created_at', ['created_at'])


def downgrade() -> None:
    # Remove created_at column from grocery_list_items table
    with op.batch_alter_table('grocery_list_items', schema=None) as batch_op:
        batch_op.drop_index('ix_grocery_list_items_created_at')
        batch_op.drop_column('created_at')
