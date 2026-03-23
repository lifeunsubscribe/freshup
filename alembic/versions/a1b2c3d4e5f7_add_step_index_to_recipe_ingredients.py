"""add_step_index_to_recipe_ingredients

Revision ID: a1b2c3d4e5f7
Revises: f9d8c7b6a5e4
Create Date: 2026-03-23 01:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, None] = 'f9d8c7b6a5e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add step_index column to recipe_ingredients table
    with op.batch_alter_table('recipe_ingredients', schema=None) as batch_op:
        batch_op.add_column(sa.Column('step_index', sa.Integer(), nullable=True))


def downgrade() -> None:
    # Remove step_index column from recipe_ingredients table
    with op.batch_alter_table('recipe_ingredients', schema=None) as batch_op:
        batch_op.drop_column('step_index')
