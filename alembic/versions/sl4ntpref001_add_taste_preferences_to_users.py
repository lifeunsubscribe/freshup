"""add taste_preferences and onboarded_at to users

Adds a graded preference map (love/like/less/never) over ingredient and cuisine
keys, and records when onboarding was completed.

Data step: folds existing favorite_ingredients → "love" and
disliked_ingredients → "never" using keys_for to normalise free-text names.
Existing users receive onboarded_at = created_at.

Revision ID: sl4ntpref001
Revises: hfcolparent01
Create Date: 2026-11-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'sl4ntpref001'
down_revision: Union[str, None] = 'hfcolparent01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add taste_preferences and onboarded_at columns, then fold old lists."""
    op.add_column('users', sa.Column('taste_preferences', sa.JSON(), nullable=True, server_default='{}'))
    op.add_column('users', sa.Column('onboarded_at', sa.DateTime(), nullable=True))

    # Data migration: fold existing favorite/disliked lists into taste_preferences
    # and set onboarded_at = created_at for existing users.
    _migrate_existing_users()


def downgrade() -> None:
    """Remove taste_preferences and onboarded_at columns."""
    op.drop_column('users', 'onboarded_at')
    op.drop_column('users', 'taste_preferences')


def _migrate_existing_users() -> None:
    """
    Copy existing ingredient lists into taste_preferences and stamp onboarded_at.

    Uses keys_for to normalise free-text ingredient names to canonical keys.
    Entries that match no known key are skipped. Rows where keys_for is
    unavailable (e.g. env without app installed) are left with empty prefs.
    """
    try:
        from src.services.ingredient_keys import keys_for
        _has_keys_for = True
    except ImportError:
        _has_keys_for = False

    import json

    bind = op.get_bind()

    rows = bind.execute(
        sa.text("SELECT id, favorite_ingredients, disliked_ingredients, created_at FROM users")
    ).fetchall()

    for row in rows:
        user_id = row[0]
        raw_favorites = row[1]
        raw_disliked = row[2]
        created_at = row[3]

        # JSON may be stored as string (SQLite) or already decoded (Postgres)
        favorites = _decode_json_list(raw_favorites)
        disliked = _decode_json_list(raw_disliked)

        prefs: dict = {}
        if _has_keys_for:
            for name in favorites:
                for key in keys_for(name):
                    # earlier entries win; don't overwrite if already set
                    if f"ingredient:{key}" not in prefs:
                        prefs[f"ingredient:{key}"] = "love"
            for name in disliked:
                for key in keys_for(name):
                    if f"ingredient:{key}" not in prefs:
                        prefs[f"ingredient:{key}"] = "never"

        bind.execute(
            sa.text(
                "UPDATE users SET taste_preferences = :prefs, onboarded_at = :ts WHERE id = :uid"
            ),
            {"prefs": json.dumps(prefs), "ts": created_at, "uid": str(user_id)},
        )


def _decode_json_list(value) -> list:
    """Return a Python list from a value that may be a JSON string, list, or None."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    try:
        import json
        result = json.loads(value)
        return result if isinstance(result, list) else []
    except (TypeError, ValueError):
        return []
