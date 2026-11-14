"""fix hellofresh card image urls missing /hellofresh_s3

The collection crawler built card image URLs without the /hellofresh_s3 path
segment, so every stored card image 404s on the CDN. Rewrite the stored rows;
the crawler prefix is fixed in the same change.

Revision ID: hf8img3s3fix
Revises: rk3mshza1txb
Create Date: 2026-11-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'hf8img3s3fix'
down_revision: Union[str, None] = 'rk3mshza1txb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BROKEN = 'https://img.hellofresh.com/f_auto,fl_lossy,q_auto,w_600/image/'
FIXED = 'https://img.hellofresh.com/f_auto,fl_lossy,q_auto,w_600/hellofresh_s3/image/'


def _rewrite(old: str, new: str) -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE source_recipe_cards "
            "SET image_url = :new || substr(image_url, :cut) "
            "WHERE image_url LIKE :pattern"
        ),
        {"new": new, "cut": len(old) + 1, "pattern": old + '%'},
    )


def upgrade() -> None:
    """Insert /hellofresh_s3 into stored card image URLs."""
    _rewrite(BROKEN, FIXED)


def downgrade() -> None:
    """Restore the original (broken) card image URLs."""
    _rewrite(FIXED, BROKEN)
