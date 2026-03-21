"""add_timestamps_to_recipe_models

Revision ID: f9d8c7b6a5e4
Revises: 2e3ac317ae24
Create Date: 2026-03-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9d8c7b6a5e4'
down_revision: Union[str, None] = '2e3ac317ae24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add created_at and updated_at to recipes table
    with op.batch_alter_table('recipes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False))
        batch_op.create_index('ix_recipes_created_at', ['created_at'])

    # Add created_at to recipe_ingredients table
    with op.batch_alter_table('recipe_ingredients', schema=None) as batch_op:
        batch_op.add_column(sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False))

    # Add created_at and updated_at to user_recipe_ratings table
    with op.batch_alter_table('user_recipe_ratings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False))


def downgrade() -> None:
    # Remove timestamps from user_recipe_ratings table
    with op.batch_alter_table('user_recipe_ratings', schema=None) as batch_op:
        batch_op.drop_column('updated_at')
        batch_op.drop_column('created_at')

    # Remove created_at from recipe_ingredients table
    with op.batch_alter_table('recipe_ingredients', schema=None) as batch_op:
        batch_op.drop_column('created_at')

    # Remove timestamps from recipes table
    with op.batch_alter_table('recipes', schema=None) as batch_op:
        batch_op.drop_index('ix_recipes_created_at')
        batch_op.drop_column('updated_at')
        batch_op.drop_column('created_at')
