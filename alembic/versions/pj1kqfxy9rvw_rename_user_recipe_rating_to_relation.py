"""rename user_recipe_rating to relation

Revision ID: pj1kqfxy9rvw
Revises: oi0jpexw8quw
Create Date: 2026-05-03 17:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'pj1kqfxy9rvw'
down_revision: Union[str, None] = 'oi0jpexw8quw'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Rename user_recipe_ratings table to user_recipe_relations and add new fields.

    Migration sequence:
    1. Rename table
    2. Add new columns
    3. Migrate data from old columns to new columns
    4. Drop old columns
    5. Rename unique constraint
    """
    # Step 1: Rename table and update constraint
    with op.batch_alter_table('user_recipe_ratings', schema=None) as batch_op:
        batch_op.drop_constraint('uq_user_recipe_rating', type_='unique')

    op.rename_table('user_recipe_ratings', 'user_recipe_relations')

    # Step 2: Add new columns
    with op.batch_alter_table('user_recipe_relations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_bookmarked', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('is_liked', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('rating_photos', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('rating_comment', sa.String(2000), nullable=True))

        # Add renamed unique constraint
        batch_op.create_unique_constraint('uq_user_recipe_relation', ['user_id', 'recipe_id'])

    # Step 3: Migrate data - copy is_favorite to is_bookmarked, notes to rating_comment
    op.execute(
        'UPDATE user_recipe_relations SET is_bookmarked = is_favorite WHERE is_favorite = 1'
    )
    op.execute(
        'UPDATE user_recipe_relations SET rating_comment = notes WHERE notes IS NOT NULL'
    )

    # Step 4: Drop old columns
    with op.batch_alter_table('user_recipe_relations', schema=None) as batch_op:
        batch_op.drop_column('is_favorite')
        batch_op.drop_column('notes')


def downgrade() -> None:
    """Reverse the migration - restore user_recipe_ratings table."""
    # Add back old columns
    with op.batch_alter_table('user_recipe_relations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_favorite', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('notes', sa.String(1000), nullable=True))

    # Migrate data back
    op.execute(
        'UPDATE user_recipe_relations SET is_favorite = is_bookmarked WHERE is_bookmarked = 1'
    )
    op.execute(
        'UPDATE user_recipe_relations SET notes = SUBSTR(rating_comment, 1, 1000) WHERE rating_comment IS NOT NULL'
    )

    # Drop new columns
    with op.batch_alter_table('user_recipe_relations', schema=None) as batch_op:
        batch_op.drop_constraint('uq_user_recipe_relation', type_='unique')
        batch_op.drop_column('rating_comment')
        batch_op.drop_column('rating_photos')
        batch_op.drop_column('is_liked')
        batch_op.drop_column('is_bookmarked')

    # Rename table back
    op.rename_table('user_recipe_relations', 'user_recipe_ratings')

    # Restore original constraint
    with op.batch_alter_table('user_recipe_ratings', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_user_recipe_rating', ['user_id', 'recipe_id'])
