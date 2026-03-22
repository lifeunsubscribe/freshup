"""add_compound_index_to_grocery_list_items

Adds compound index on (purchased, created_at) to grocery_list_items table
to optimize the common query pattern: filtering by purchased status and
ordering by creation timestamp.

This compound index replaces the single-column index on created_at from
migration a1b2c3d4e5f6. The compound index can efficiently handle both
the WHERE clause on purchased and the ORDER BY clause on created_at,
improving query performance for list_items() and get_items_by_store().

Query patterns optimized:
- WHERE purchased = ? ORDER BY created_at DESC (list_items)
- WHERE purchased = ? ORDER BY created_at DESC (get_items_by_store)

Index column order follows database best practice: filter columns first
(purchased), then ordering columns (created_at).

Revision ID: b1c2d3e4f5g6
Revises: a1b2c3d4e5f6
Create Date: 2026-03-21 18:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5g6'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Replace single-column index with compound index for better query performance
    with op.batch_alter_table('grocery_list_items', schema=None) as batch_op:
        # Drop the old single-column index on created_at
        batch_op.drop_index('ix_grocery_list_items_created_at')
        # Create compound index: purchased first (filter), then created_at (ordering)
        batch_op.create_index('ix_grocery_list_items_purchased_created_at', ['purchased', 'created_at'])


def downgrade() -> None:
    # Restore the original single-column index
    with op.batch_alter_table('grocery_list_items', schema=None) as batch_op:
        # Drop the compound index
        batch_op.drop_index('ix_grocery_list_items_purchased_created_at')
        # Restore the original single-column index on created_at
        batch_op.create_index('ix_grocery_list_items_created_at', ['created_at'])
