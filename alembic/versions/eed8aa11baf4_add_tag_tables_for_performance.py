"""add_tag_tables_for_performance

Revision ID: eed8aa11baf4
Revises: b55e4387092a
Create Date: 2026-05-03 18:11:04.200192

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eed8aa11baf4'
down_revision: Union[str, None] = 'b55e4387092a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add tags and recipe_tags tables for optimized tag-based queries.

    Replaces the inefficient JSON-based tag filtering (which required full table
    scans) with indexed many-to-many relationships. This enables O(log n) queries
    instead of O(n) for tag-based recipe lookups.

    Migration also backfills existing recipe tags from the JSON column into the
    new junction table to maintain data integrity.
    """
    # Create tags table
    op.create_table(
        'tags',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # Create index on tag name for efficient lookups
    op.create_index('ix_tags_name', 'tags', ['name'])

    # Create recipe_tags junction table
    op.create_table(
        'recipe_tags',
        sa.Column('recipe_id', sa.Uuid(), nullable=False),
        sa.Column('tag_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['recipe_id'], ['recipes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('recipe_id', 'tag_id')
    )

    # Create index on tag_id for efficient reverse lookups (find recipes by tag)
    op.create_index('ix_recipe_tags_tag_id', 'recipe_tags', ['tag_id'])

    # Backfill existing tags from JSON column to new tables
    # This is safe because we're reading from JSON and writing to new tables
    op.execute("""
        INSERT INTO tags (name)
        SELECT DISTINCT json_each.value
        FROM recipes, json_each(recipes.tags)
        WHERE recipes.tags IS NOT NULL AND recipes.tags != '[]'
        ORDER BY json_each.value
    """)

    # Populate recipe_tags junction table from existing recipe.tags JSON
    op.execute("""
        INSERT INTO recipe_tags (recipe_id, tag_id)
        SELECT DISTINCT recipes.id, tags.id
        FROM recipes, json_each(recipes.tags), tags
        WHERE recipes.tags IS NOT NULL
          AND recipes.tags != '[]'
          AND json_each.value = tags.name
    """)


def downgrade() -> None:
    """
    Remove tags and recipe_tags tables.

    Note: This does NOT restore the JSON column data, as it's assumed the
    JSON column was never removed. If you need to restore tag data, you'll
    need to manually migrate from the junction table back to JSON.
    """
    op.drop_index('ix_recipe_tags_tag_id', table_name='recipe_tags')
    op.drop_table('recipe_tags')
    op.drop_index('ix_tags_name', table_name='tags')
    op.drop_table('tags')
