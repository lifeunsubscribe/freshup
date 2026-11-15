"""add ingredient_keys to source_recipe_cards

Adds a nullable JSON column to store the sorted ingredient keys extracted from
the recipe when a card is opened. NULL means the card has not been imported yet;
[] means it was imported and no known ingredients matched.

Revision ID: carding01
Revises: hfcolparent01
Create Date: 2026-11-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'carding01'
down_revision: Union[str, None] = 'hfcolparent01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'source_recipe_cards',
        sa.Column('ingredient_keys', sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('source_recipe_cards', 'ingredient_keys')
