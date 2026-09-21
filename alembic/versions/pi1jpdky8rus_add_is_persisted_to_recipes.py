"""add is_persisted to recipes

Revision ID: pi1jpdky8rus
Revises: nh9iocxw7qtv
Create Date: 2026-05-03 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'pi1jpdky8rus'
down_revision: Union[str, None] = 'nh9iocxw7qtv'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add is_persisted column to recipes table.

    This field tracks whether a recipe should be kept permanently (True) or is
    eligible for cleanup as part of the browse cache (False). Scraped recipes
    start as non-persisted and become persisted through user interaction
    (bookmarking, cooking, rating, adding to menu, etc.).

    Backfills existing recipes with is_persisted=True since they were created
    before the browse-then-persist flow was implemented.
    """
    with op.batch_alter_table('recipes', schema=None) as batch_op:
        # Add column with default False for new rows
        batch_op.add_column(
            sa.Column('is_persisted', sa.Boolean(), nullable=False, server_default=sa.false())
        )

    # Backfill existing recipes as persisted
    # (they exist in production, so should be kept)
    op.execute(
        sa.text("UPDATE recipes SET is_persisted = true")
    )


def downgrade() -> None:
    """Remove is_persisted column from recipes table.

    Guards against the sibling migration oi0jpexw8quw, which revises the same
    parent (nh9iocxw7qtv) and also adds is_persisted (with an index).  When
    downgrading from head to base, oi0jpexw8quw's downgrade runs before this
    one (it sits deeper in the qk2lrgyz0swx→pj1kqfxy9rvw→oi0jpexw8quw chain),
    so the column may already be gone.  Attempting drop_column on a
    non-existent column raises OperationalError on SQLite and would abort the
    entire downgrade chain, so we skip gracefully when the column is absent.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("recipes")}
    if "is_persisted" not in columns:
        return
    with op.batch_alter_table('recipes', schema=None) as batch_op:
        batch_op.drop_column('is_persisted')
