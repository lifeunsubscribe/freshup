"""clean unit periods from ingredient names

Home Chef writes units with periods ("8 oz. Shrimp", "3 fl. oz. Liquid Egg").
The ingredient parser took the unit and left ". Shrimp", or missed "fl. oz."
and left "fl. oz. Liquid Egg" with no unit. The parser is fixed; this cleans
what was already stored, in recipes and on the grocery list.

Data only: no schema change. Downgrade leaves the cleaned names.

Revision ID: ip4hx7nq2kzd
Revises: vr3nq8kx5wpd
Create Date: 2026-11-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'ip4hx7nq2kzd'
down_revision: Union[str, None] = 'vr3nq8kx5wpd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLES = (
    # (table, name column)
    ("recipe_ingredients", "ingredient_name"),
    ("grocery_list_items", "item_name"),
)


def upgrade() -> None:
    for table, name in _TABLES:
        # "fl. oz. Liquid Egg" with no unit -> unit "fl oz", name "Liquid Egg".
        op.execute(
            f"UPDATE {table} SET unit = 'fl oz', {name} = TRIM(SUBSTR({name}, 8)) "
            f"WHERE (unit = '' OR unit IS NULL) AND LOWER({name}) LIKE 'fl. oz. %'"
        )
        # ". Shrimp" -> "Shrimp".
        op.execute(
            f"UPDATE {table} SET {name} = TRIM(SUBSTR({name}, 2)) "
            f"WHERE {name} LIKE '. %'"
        )


def downgrade() -> None:
    pass
