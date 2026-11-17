"""add catalog_card_id to meal_plan_entries

Links a draft entry to a catalog card that has not yet been imported.
The column is set at draft-generation time and cleared (recipe_id takes
over) when the user confirms the entry and open_card imports the recipe.

Revision ID: un6pvkca4wzd
Revises: sl4ntia2uyc
Create Date: 2026-11-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'un6pvkca4wzd'
down_revision: Union[str, None] = 'sl4ntia2uyc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('meal_plan_entries', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('catalog_card_id', sa.UUID(), nullable=True)
        )
        batch_op.create_foreign_key(
            'fk_meal_plan_entries_catalog_card_id_source_recipe_cards',
            'source_recipe_cards',
            ['catalog_card_id'],
            ['id'],
            ondelete='SET NULL',
        )


def downgrade() -> None:
    with op.batch_alter_table('meal_plan_entries', schema=None) as batch_op:
        batch_op.drop_constraint(
            'fk_meal_plan_entries_catalog_card_id_source_recipe_cards',
            type_='foreignkey',
        )
        batch_op.drop_column('catalog_card_id')
