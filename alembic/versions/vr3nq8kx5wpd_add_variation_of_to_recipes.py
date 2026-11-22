"""add variation_of to recipes

A user's own version of a recipe is a copy that points at the original.

Revision ID: vr3nq8kx5wpd
Revises: gs8mw4pq2ztx
Create Date: 2026-11-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'vr3nq8kx5wpd'
down_revision: Union[str, None] = 'gs8mw4pq2ztx'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('recipes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('variation_of', sa.UUID(), nullable=True))
        batch_op.create_foreign_key(
            'fk_recipes_variation_of_recipes',
            'recipes',
            ['variation_of'],
            ['id'],
            ondelete='SET NULL',
        )
        batch_op.create_index('ix_recipes_variation_of', ['variation_of'])


def downgrade() -> None:
    with op.batch_alter_table('recipes', schema=None) as batch_op:
        batch_op.drop_index('ix_recipes_variation_of')
        batch_op.drop_constraint('fk_recipes_variation_of_recipes', type_='foreignkey')
        batch_op.drop_column('variation_of')
