"""add case insensitive indexes

Revision ID: rl3mshjz1tyx
Revises: qk2lrgyz0swx
Create Date: 2026-05-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'rl3mshjz1tyx'
down_revision: Union[str, None] = 'qk2lrgyz0swx'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create case-insensitive indexes for efficient case-insensitive matching
    # COLLATE NOCASE enables SQLite to use these indexes for case-insensitive comparisons

    # Index on recipe_ingredients.ingredient_name for join performance
    op.create_index(
        'ix_recipe_ingredients_ingredient_name_nocase',
        'recipe_ingredients',
        [sa.text('ingredient_name COLLATE NOCASE')]
    )

    # Index on inventory_items.name for join performance
    op.create_index(
        'ix_inventory_items_name_nocase',
        'inventory_items',
        [sa.text('name COLLATE NOCASE')]
    )

    # Index on stores.name for lookup performance
    # Note: stores.name already has a unique constraint, but add case-insensitive index
    op.create_index(
        'ix_stores_name_nocase',
        'stores',
        [sa.text('name COLLATE NOCASE')]
    )


def downgrade() -> None:
    # Drop case-insensitive indexes
    op.drop_index('ix_stores_name_nocase', table_name='stores')
    op.drop_index('ix_inventory_items_name_nocase', table_name='inventory_items')
    op.drop_index('ix_recipe_ingredients_ingredient_name_nocase', table_name='recipe_ingredients')
