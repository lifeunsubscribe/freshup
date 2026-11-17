"""add catalog_card_id to meal_plan_entries

Adds a nullable FK column so a draft entry can point at a catalog card that
has not yet been imported as a Recipe. The column is cleared (SET NULL) when
the referenced card row is deleted, so the entry degrades gracefully.

Revision ID: mp603a
Revises: sl4ntia2uyc
Create Date: 2026-11-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'mp603a'
down_revision: Union[str, None] = 'sl4ntia2uyc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("meal_plan_entries") as batch_op:
        batch_op.add_column(
            sa.Column(
                "catalog_card_id",
                sa.Uuid(),
                sa.ForeignKey("source_recipe_cards.id", ondelete="SET NULL"),
                nullable=True,
            )
        )
        batch_op.create_index(
            "ix_meal_plan_entries_catalog_card_id",
            ["catalog_card_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("meal_plan_entries") as batch_op:
        batch_op.drop_index("ix_meal_plan_entries_catalog_card_id")
        batch_op.drop_column("catalog_card_id")
