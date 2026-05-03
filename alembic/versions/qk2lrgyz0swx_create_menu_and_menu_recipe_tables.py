"""create menu and menu_recipe tables

Revision ID: qk2lrgyz0swx
Revises: pj1kqfxy9rvw
Create Date: 2026-05-03 17:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'qk2lrgyz0swx'
down_revision: Union[str, None] = 'pj1kqfxy9rvw'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create menus and menu_recipes tables."""
    # Create menus table
    op.create_table(
        'menus',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('filter_rules', sa.JSON(), nullable=True),
        sa.Column('is_auto_generated', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('cover_image', sa.String(2048), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_menus_user_id_users'),
    )

    # Create menu_recipes join table
    op.create_table(
        'menu_recipes',
        sa.Column('menu_id', sa.UUID(), nullable=False),
        sa.Column('recipe_id', sa.UUID(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('manually_added', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('manually_removed', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('added_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('menu_id', 'recipe_id'),
        sa.ForeignKeyConstraint(['menu_id'], ['menus.id'], name='fk_menu_recipes_menu_id_menus'),
        sa.ForeignKeyConstraint(['recipe_id'], ['recipes.id'], name='fk_menu_recipes_recipe_id_recipes'),
        sa.UniqueConstraint('menu_id', 'recipe_id', name='uq_menu_recipe'),
    )


def downgrade() -> None:
    """Drop menu_recipes and menus tables."""
    op.drop_table('menu_recipes')
    op.drop_table('menus')
