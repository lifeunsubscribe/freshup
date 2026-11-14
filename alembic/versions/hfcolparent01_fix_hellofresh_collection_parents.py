"""fix hellofresh collection hierarchy from urls

Two bugs left the collection tree inverted:

* The sitemap seed stored every collection as top-level, including nested
  sub-collections like /recipes/grain-recipes/arborio-rice.
* Fetching a nested slug as /recipes/<slug> served HelloFresh's /recipes hub,
  which was stored as a collection named "recipes" and adopted every real
  top-level category as its child.

The URL path is the canonical hierarchy, so recompute parent_slug from it and
drop the bogus hub row. Its join rows go with it; the cards themselves are
shared with real collections and stay.

Downgrade is a no-op: the previous state was corrupt and isn't worth restoring.

Revision ID: hfcolparent01
Revises: hf8img3s3fix
Create Date: 2026-11-12 00:00:00.000000

"""
from typing import Optional, Sequence, Union
from urllib.parse import urlparse

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'hfcolparent01'
down_revision: Union[str, None] = 'hf8img3s3fix'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SOURCE = 'hellofresh_web'
HUB_SLUG = 'recipes'


def _parent_from_url(url: str) -> Optional[str]:
    # Mirrors catalog_service._parent_slug_from_url; inlined so the migration
    # doesn't depend on application code that may change later.
    segments = urlparse(url).path.strip('/').split('/')
    return segments[-2] if len(segments) >= 3 else None


def upgrade() -> None:
    """Delete the /recipes hub row and recompute parent_slug from each URL."""
    bind = op.get_bind()

    hub_ids = [
        row[0]
        for row in bind.execute(
            sa.text("SELECT id FROM source_collections WHERE source_type = :src AND slug = :hub"),
            {"src": SOURCE, "hub": HUB_SLUG},
        )
    ]
    for hub_id in hub_ids:
        bind.execute(
            sa.text("DELETE FROM source_collection_cards WHERE collection_id = :id"), {"id": hub_id}
        )
        bind.execute(sa.text("DELETE FROM source_collections WHERE id = :id"), {"id": hub_id})

    rows = bind.execute(
        sa.text("SELECT id, url, parent_slug FROM source_collections WHERE source_type = :src"),
        {"src": SOURCE},
    ).fetchall()
    for coll_id, url, parent_slug in rows:
        correct = _parent_from_url(url)
        if correct != parent_slug:
            bind.execute(
                sa.text("UPDATE source_collections SET parent_slug = :p WHERE id = :id"),
                {"p": correct, "id": coll_id},
            )


def downgrade() -> None:
    """No-op: the pre-upgrade hierarchy was corrupt."""
    pass
