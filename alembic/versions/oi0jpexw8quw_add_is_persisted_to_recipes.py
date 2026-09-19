"""add is_persisted to recipes

Revision ID: oi0jpexw8quw
Revises: nh9iocxw7qtv
Create Date: 2026-05-03 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'oi0jpexw8quw'
down_revision: Union[str, None] = 'nh9iocxw7qtv'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add is_persisted column to recipes table.

    This field tracks whether a recipe should be kept permanently (True) or is
    eligible for cleanup as part of the browse cache (False). Scraped recipes
    start as non-persisted and become persisted through user interaction
    (bookmarking, liking, adding to a meal plan or menu).

    The server_default is true, matching Recipe.is_persisted (default=True).
    Only the scraper path marks a recipe False explicitly. Defaulting to true
    also backfills every pre-existing row as persisted, which is correct: they
    predate the browse-then-persist flow and must never be pruned.
    """
    with op.batch_alter_table('recipes', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('is_persisted', sa.Boolean(), nullable=False, server_default=sa.true())
        )
        # cleanup_service filters on is_persisted == False to prune the browse
        # cache, and the feed queries filter on is_persisted == True.
        batch_op.create_index('ix_recipes_is_persisted', ['is_persisted'])


def downgrade() -> None:
    """Remove is_persisted column from recipes table."""
    with op.batch_alter_table('recipes', schema=None) as batch_op:
        batch_op.drop_index('ix_recipes_is_persisted')
        batch_op.drop_column('is_persisted')
