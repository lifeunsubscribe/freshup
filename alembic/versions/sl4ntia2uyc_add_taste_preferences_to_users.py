"""add taste_preferences and onboarded_at to users

Revision ID: sl4ntia2uyc
Revises: rk3mshza1txb
Create Date: 2026-11-15 00:00:00.000000

"""
from typing import Sequence, Union
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy import Table, MetaData


# revision identifiers, used by Alembic.
revision: str = 'sl4ntia2uyc'
down_revision: Union[str, None] = 'rk3mshza1txb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add taste_preferences and onboarded_at columns to users table, then fold old lists."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('taste_preferences', sa.JSON(), nullable=False, server_default='{}')
        )
        batch_op.add_column(
            sa.Column('onboarded_at', sa.DateTime(), nullable=True)
        )

    # Data migration: fold favorite_ingredients → love, disliked_ingredients → never.
    # keys_for() is imported inline so the migration stays correct for the vocabulary
    # that existed when this migration was written (Phase 2.5J, 2026-11-15).
    from src.services.ingredient_keys import keys_for

    connection = op.get_bind()
    metadata = MetaData()
    users_table = Table('users', metadata, autoload_with=connection)

    rows = connection.execute(
        sa.select(
            users_table.c.id,
            users_table.c.favorite_ingredients,
            users_table.c.disliked_ingredients,
            users_table.c.created_at,
        )
    ).fetchall()

    for row in rows:
        prefs: dict[str, str] = {}

        # SQLite stores JSON as text; handle both serialised strings and Python lists.
        fav = row.favorite_ingredients
        if isinstance(fav, str):
            fav = json.loads(fav) if fav else []
        disliked = row.disliked_ingredients
        if isinstance(disliked, str):
            disliked = json.loads(disliked) if disliked else []

        for name in (fav or []):
            for key in keys_for(name):
                prefs[f"ingredient:{key}"] = "love"

        for name in (disliked or []):
            for key in keys_for(name):
                # love wins: if same key appears in both lists, keep "love"
                pref_key = f"ingredient:{key}"
                if pref_key not in prefs:
                    prefs[pref_key] = "never"

        connection.execute(
            users_table.update()
            .where(users_table.c.id == row.id)
            .values(taste_preferences=prefs, onboarded_at=row.created_at)
        )


def downgrade() -> None:
    """Remove taste_preferences and onboarded_at columns from users table."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('onboarded_at')
        batch_op.drop_column('taste_preferences')
