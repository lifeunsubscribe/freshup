"""create source catalog tables

Revision ID: 233fdf1bfa0c
Revises: 329de0a8bc02
Create Date: 2026-11-11 01:26:48.594919

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '233fdf1bfa0c'
down_revision: Union[str, None] = '329de0a8bc02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('source_collections',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('source_type', sa.String(length=50), nullable=False),
    sa.Column('slug', sa.String(length=255), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('parent_slug', sa.String(length=255), nullable=True),
    sa.Column('url', sa.String(length=2048), nullable=False),
    sa.Column('last_fetched_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('source_type', 'slug', name='uq_source_collections_source_type_slug')
    )
    with op.batch_alter_table('source_collections', schema=None) as batch_op:
        batch_op.create_index('ix_source_collections_parent_slug', ['parent_slug'], unique=False)

    op.create_table('source_recipe_cards',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('source_type', sa.String(length=50), nullable=False),
    sa.Column('external_id', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('headline', sa.String(length=500), nullable=True),
    sa.Column('image_url', sa.String(length=2048), nullable=True),
    sa.Column('prep_time_minutes', sa.Integer(), nullable=True),
    sa.Column('rating', sa.Float(), nullable=True),
    sa.Column('rating_count', sa.Integer(), nullable=True),
    sa.Column('recipe_url', sa.String(length=2048), nullable=False),
    sa.Column('recipe_id', sa.Uuid(), nullable=True),
    sa.Column('fetched_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['recipe_id'], ['recipes.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('source_type', 'recipe_url', name='uq_source_recipe_cards_source_type_recipe_url')
    )
    with op.batch_alter_table('source_recipe_cards', schema=None) as batch_op:
        batch_op.create_index('ix_source_recipe_cards_recipe_id', ['recipe_id'], unique=False)

    op.create_table('source_collection_cards',
    sa.Column('collection_id', sa.Uuid(), nullable=False),
    sa.Column('card_id', sa.Uuid(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['card_id'], ['source_recipe_cards.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['collection_id'], ['source_collections.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('collection_id', 'card_id')
    )


def downgrade() -> None:
    op.drop_table('source_collection_cards')
    with op.batch_alter_table('source_recipe_cards', schema=None) as batch_op:
        batch_op.drop_index('ix_source_recipe_cards_recipe_id')
    op.drop_table('source_recipe_cards')
    with op.batch_alter_table('source_collections', schema=None) as batch_op:
        batch_op.drop_index('ix_source_collections_parent_slug')
    op.drop_table('source_collections')
