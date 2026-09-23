"""add cook event and view tables

Revision ID: 329de0a8bc02
Revises: dea9fe233cdb
Create Date: 2026-09-22 20:06:21.919463

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '329de0a8bc02'
down_revision: Union[str, None] = 'dea9fe233cdb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create user_cook_events and user_recipe_views tables."""
    # Create user_cook_events table.
    # No unique constraint — a user can cook the same recipe multiple times.
    op.create_table(
        'user_cook_events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('recipe_id', sa.Uuid(), nullable=False),
        sa.Column('cooked_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('meal_plan_entry_id', sa.Uuid(), nullable=True),
        sa.Column('notes', sa.String(500), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'],
            name='fk_user_cook_events_user_id_users',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['recipe_id'], ['recipes.id'],
            name='fk_user_cook_events_recipe_id_recipes',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['meal_plan_entry_id'], ['meal_plan_entries.id'],
            name='fk_user_cook_events_meal_plan_entry_id_meal_plan_entries',
            ondelete='SET NULL',
        ),
    )
    op.create_index('ix_user_cook_events_user_id', 'user_cook_events', ['user_id'])
    op.create_index('ix_user_cook_events_recipe_id', 'user_cook_events', ['recipe_id'])
    op.create_index('ix_user_cook_events_meal_plan_entry_id', 'user_cook_events', ['meal_plan_entry_id'])

    # Create user_recipe_views table.
    # No unique constraint — repeat views are each recorded; the feed signal
    # compares view count to cook count to surface viewed-but-not-cooked recipes.
    op.create_table(
        'user_recipe_views',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('recipe_id', sa.Uuid(), nullable=False),
        sa.Column('viewed_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('source', sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'],
            name='fk_user_recipe_views_user_id_users',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['recipe_id'], ['recipes.id'],
            name='fk_user_recipe_views_recipe_id_recipes',
            ondelete='CASCADE',
        ),
    )
    op.create_index('ix_user_recipe_views_user_id', 'user_recipe_views', ['user_id'])
    op.create_index('ix_user_recipe_views_recipe_id', 'user_recipe_views', ['recipe_id'])


def downgrade() -> None:
    """Drop user_cook_events and user_recipe_views tables."""
    op.drop_index('ix_user_recipe_views_recipe_id', table_name='user_recipe_views')
    op.drop_index('ix_user_recipe_views_user_id', table_name='user_recipe_views')
    op.drop_table('user_recipe_views')

    op.drop_index('ix_user_cook_events_meal_plan_entry_id', table_name='user_cook_events')
    op.drop_index('ix_user_cook_events_recipe_id', table_name='user_cook_events')
    op.drop_index('ix_user_cook_events_user_id', table_name='user_cook_events')
    op.drop_table('user_cook_events')
