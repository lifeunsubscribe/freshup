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
    """Add is_persisted column to recipes table with default true."""
    with op.batch_alter_table('recipes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_persisted', sa.Boolean(), nullable=False, server_default='1'))
        batch_op.create_index('ix_recipes_is_persisted', ['is_persisted'])


def downgrade() -> None:
    """Remove is_persisted column from recipes table.

    Guards against the sibling migration pi1jpdky8rus, which revises the same
    parent (nh9iocxw7qtv) and also adds is_persisted (without an index).  When
    upgrading from base to head, pi1jpdky8rus.upgrade() runs a batch_alter_table
    on the recipes table AFTER this migration's upgrade created
    ix_recipes_is_persisted.  SQLite batch mode rebuilds the table without
    preserving indexes that were not re-declared within that batch context, so
    the index may already be gone by the time this downgrade runs.  Attempting
    to drop a non-existent index raises OperationalError on SQLite and would
    abort the entire downgrade chain, so we skip gracefully when absent.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("recipes")}
    with op.batch_alter_table('recipes', schema=None) as batch_op:
        if "ix_recipes_is_persisted" in existing_indexes:
            batch_op.drop_index('ix_recipes_is_persisted')
        batch_op.drop_column('is_persisted')
