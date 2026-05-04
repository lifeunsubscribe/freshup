"""add lowercase columns for case-insensitive matching

Revision ID: dae9onwpk4jh
Revises: lf9gmzbv5orr
Create Date: 2026-04-04 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dae9onwpk4jh'
down_revision: Union[str, None] = 'lf9gmzbv5orr'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add normalized lowercase columns to enable efficient case-insensitive matching.

    This migration addresses the performance issue identified in issue #477 where
    func.lower() on both sides of joins prevents index usage and causes table scans.

    Changes:
    - Add ingredient_name_lower to recipe_ingredients with index
    - Add name_lower to inventory_items with index
    - Add name_lower to stores with unique index (stores.name is unique)
    - Backfill existing data with lowercase values

    After this migration, queries can use direct comparisons on normalized columns
    instead of func.lower() calls, enabling database index usage for better performance.
    """

    # Add ingredient_name_lower to recipe_ingredients
    with op.batch_alter_table('recipe_ingredients', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('ingredient_name_lower', sa.String(255), nullable=True)
        )

    # Backfill ingredient_name_lower with lowercase values
    op.execute(
        sa.text("UPDATE recipe_ingredients SET ingredient_name_lower = LOWER(ingredient_name)")
    )

    # Make ingredient_name_lower NOT NULL after backfill
    with op.batch_alter_table('recipe_ingredients', schema=None) as batch_op:
        batch_op.alter_column('ingredient_name_lower', nullable=False)
        # Create index for case-insensitive matching performance
        batch_op.create_index(
            'ix_recipe_ingredients_ingredient_name_lower',
            ['ingredient_name_lower']
        )

    # Add name_lower to inventory_items
    with op.batch_alter_table('inventory_items', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('name_lower', sa.String(255), nullable=True)
        )

    # Backfill name_lower with lowercase values
    op.execute(
        sa.text("UPDATE inventory_items SET name_lower = LOWER(name)")
    )

    # Make name_lower NOT NULL after backfill
    with op.batch_alter_table('inventory_items', schema=None) as batch_op:
        batch_op.alter_column('name_lower', nullable=False)
        # Create index for case-insensitive matching performance
        batch_op.create_index(
            'ix_inventory_items_name_lower',
            ['name_lower']
        )

    # Add name_lower to stores
    with op.batch_alter_table('stores', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('name_lower', sa.String(255), nullable=True)
        )

    # Backfill name_lower with lowercase values
    op.execute(
        sa.text("UPDATE stores SET name_lower = LOWER(name)")
    )

    # Make name_lower NOT NULL after backfill and add unique constraint
    # (stores.name is unique, so name_lower should be unique too)
    with op.batch_alter_table('stores', schema=None) as batch_op:
        batch_op.alter_column('name_lower', nullable=False)
        # Create unique index for case-insensitive lookups
        batch_op.create_index(
            'ix_stores_name_lower',
            ['name_lower'],
            unique=True
        )


def downgrade() -> None:
    """Remove normalized lowercase columns and their indexes."""

    # Remove columns and indexes from recipe_ingredients
    with op.batch_alter_table('recipe_ingredients', schema=None) as batch_op:
        batch_op.drop_index('ix_recipe_ingredients_ingredient_name_lower')
        batch_op.drop_column('ingredient_name_lower')

    # Remove columns and indexes from inventory_items
    with op.batch_alter_table('inventory_items', schema=None) as batch_op:
        batch_op.drop_index('ix_inventory_items_name_lower')
        batch_op.drop_column('name_lower')

    # Remove columns and indexes from stores
    with op.batch_alter_table('stores', schema=None) as batch_op:
        batch_op.drop_index('ix_stores_name_lower')
        batch_op.drop_column('name_lower')
