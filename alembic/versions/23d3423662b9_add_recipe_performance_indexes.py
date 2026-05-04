"""add_recipe_performance_indexes

Revision ID: 23d3423662b9
Revises: pi1jpdky8rus
Create Date: 2026-05-03 18:22:55.485483

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '23d3423662b9'
down_revision: Union[str, None] = 'pi1jpdky8rus'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add indexes to improve query performance for feed service queries
    # These indexes target common WHERE and ORDER BY patterns used in:
    # - get_recipes_by_tag() - filters by is_persisted, sorts by times_cooked
    # - get_recipes_by_source() - filters by is_persisted + source_type
    # - get_popular_recipes() - filters by is_persisted, sorts by times_cooked
    # - get_quick_recipes() - filters by is_persisted + cook_time
    # - get_new_recipes() - filters by is_persisted, sorts by created_at

    # Index for is_persisted filtering (used in almost all feed queries)
    op.create_index('ix_recipes_is_persisted', 'recipes', ['is_persisted'])

    # Composite index for popular/most-cooked queries
    # SQLite can use this for: WHERE is_persisted=true ORDER BY times_cooked DESC
    op.create_index(
        'ix_recipes_persisted_times_cooked',
        'recipes',
        ['is_persisted', 'times_cooked'],
        postgresql_ops={'times_cooked': 'DESC'}
    )

    # Index for source-based filtering
    op.create_index('ix_recipes_source_type', 'recipes', ['source_type'])

    # Composite index for source + persisted queries
    op.create_index(
        'ix_recipes_persisted_source',
        'recipes',
        ['is_persisted', 'source_type']
    )

    # Composite index for new recipes queries (already has ix_recipes_created_at)
    # This composite index is more efficient for WHERE is_persisted=true ORDER BY created_at
    op.create_index(
        'ix_recipes_persisted_created_at',
        'recipes',
        ['is_persisted', 'created_at'],
        postgresql_ops={'created_at': 'DESC'}
    )

    # Index for cook_time filtering (quick meals)
    op.create_index('ix_recipes_cook_time', 'recipes', ['cook_time_minutes'])


def downgrade() -> None:
    # Drop indexes in reverse order
    op.drop_index('ix_recipes_cook_time', table_name='recipes')
    op.drop_index('ix_recipes_persisted_created_at', table_name='recipes')
    op.drop_index('ix_recipes_persisted_source', table_name='recipes')
    op.drop_index('ix_recipes_source_type', table_name='recipes')
    op.drop_index('ix_recipes_persisted_times_cooked', table_name='recipes')
    op.drop_index('ix_recipes_is_persisted', table_name='recipes')
