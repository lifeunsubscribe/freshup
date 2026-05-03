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

    # Create index on user_id for efficient menu listing queries
    op.create_index('ix_menus_user_id', 'menus', ['user_id'])

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
        sa.ForeignKeyConstraint(['recipe_id'], ['recipes.id'], name='fk_menu_recipes_recipe_id_recipes', ondelete='CASCADE'),
        sa.UniqueConstraint('menu_id', 'recipe_id', name='uq_menu_recipe'),
    )

    # Add menu_id column to user_recipe_relations table (now that menus table exists)
    with op.batch_alter_table('user_recipe_relations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('menu_id', sa.UUID(), nullable=True))
        batch_op.create_foreign_key(
            'fk_user_recipe_relations_menu_id_menus',
            'menus',
            ['menu_id'],
            ['id'],
            ondelete='SET NULL'
        )
        # Create index on the new menu_id FK
        batch_op.create_index('ix_user_recipe_relations_menu_id', ['menu_id'])
        # Create missing indexes on existing FKs (user_id and recipe_id)
        batch_op.create_index('ix_user_recipe_relations_user_id', ['user_id'])
        batch_op.create_index('ix_user_recipe_relations_recipe_id', ['recipe_id'])


def downgrade() -> None:
    """Drop menu_recipes and menus tables."""
    # Remove menu_id column from user_recipe_relations
    with op.batch_alter_table('user_recipe_relations', schema=None) as batch_op:
        # Drop indexes created in upgrade (including the FK indexes we added)
        batch_op.drop_index('ix_user_recipe_relations_recipe_id')
        batch_op.drop_index('ix_user_recipe_relations_user_id')
        batch_op.drop_index('ix_user_recipe_relations_menu_id')
        batch_op.drop_constraint('fk_user_recipe_relations_menu_id_menus', type_='foreignkey')
        batch_op.drop_column('menu_id')

    # Drop tables
    op.drop_table('menu_recipes')
    op.drop_index('ix_menus_user_id', table_name='menus')
    op.drop_table('menus')
