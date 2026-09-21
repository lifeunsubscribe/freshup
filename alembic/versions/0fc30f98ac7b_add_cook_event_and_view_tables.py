"""add cook event and view tables

Revision ID: 0fc30f98ac7b
Revises: nh0iocxw7qtr, pi1jpdky8rus, qk2lrgyz0swx
Create Date: 2026-09-21 15:11:25.408793

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0fc30f98ac7b'
down_revision: Union[str, None] = ('nh0iocxw7qtr', 'pi1jpdky8rus', 'qk2lrgyz0swx')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create user_cook_events and user_recipe_views tables.

    Uses sa.Uuid() for all new UUID columns (not the legacy sa.UUID class) so
    these tables do not contribute to the declaration-class drift documented
    in ADR Section 13.4.
    """
    # Create user_cook_events table.
    # No unique constraint — a user can cook the same recipe many times.
    op.create_table(
        'user_cook_events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('recipe_id', sa.Uuid(), nullable=False),
        sa.Column('cooked_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('meal_plan_entry_id', sa.Uuid(), nullable=True),
        sa.Column('notes', sa.String(500), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_user_cook_events_user_id_users'),
        sa.ForeignKeyConstraint(['recipe_id'], ['recipes.id'], name='fk_user_cook_events_recipe_id_recipes'),
        sa.ForeignKeyConstraint(
            ['meal_plan_entry_id'], ['meal_plan_entries.id'],
            name='fk_user_cook_events_meal_plan_entry_id_meal_plan_entries',
        ),
    )
    op.create_index('ix_user_cook_events_user_id', 'user_cook_events', ['user_id'])
    op.create_index('ix_user_cook_events_recipe_id', 'user_cook_events', ['recipe_id'])

    # Create user_recipe_views table.
    # No unique constraint — repeat views are each recorded separately.
    op.create_table(
        'user_recipe_views',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('recipe_id', sa.Uuid(), nullable=False),
        sa.Column('viewed_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('source', sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_user_recipe_views_user_id_users'),
        sa.ForeignKeyConstraint(['recipe_id'], ['recipes.id'], name='fk_user_recipe_views_recipe_id_recipes'),
    )
    op.create_index('ix_user_recipe_views_user_id', 'user_recipe_views', ['user_id'])
    op.create_index('ix_user_recipe_views_recipe_id', 'user_recipe_views', ['recipe_id'])


def downgrade() -> None:
    """Drop user_recipe_views and user_cook_events tables."""
    op.drop_index('ix_user_recipe_views_recipe_id', table_name='user_recipe_views')
    op.drop_index('ix_user_recipe_views_user_id', table_name='user_recipe_views')
    op.drop_table('user_recipe_views')

    op.drop_index('ix_user_cook_events_recipe_id', table_name='user_cook_events')
    op.drop_index('ix_user_cook_events_user_id', table_name='user_cook_events')
    op.drop_table('user_cook_events')
