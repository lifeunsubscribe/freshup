"""seed costco store parsing profile

Revision ID: mg8hnbcw6psr
Revises: lf9gmzbv5orr
Create Date: 2026-04-04 17:00:00.000000

"""
from typing import Sequence, Union
import json
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'mg8hnbcw6psr'
down_revision: Union[str, None] = 'lf9gmzbv5orr'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Deterministic UUID for Costco store (same across all environments)
COSTCO_STORE_ID = "a1b2c3d4-e5f6-4789-0abc-def123456789"


def upgrade() -> None:
    """
    Seed Costco store with parsing profile for store-aware receipt parsing.

    The parsing_profile JSON includes:
    - item_name_patterns: Costco-specific product name patterns to recognize
    - quantity_patterns: Bulk quantity indicators (e.g., "2-pack", "24 ct")
    - price_format_hints: Price per unit displays (e.g., "$/oz", "$/lb")
    - common_abbreviations: Costco-specific abbreviations (e.g., "ORG", "KS")

    Uses INSERT OR IGNORE for idempotency (safe to run multiple times).
    """
    # Costco parsing profile with store-specific hints
    costco_profile = {
        "item_name_patterns": [
            "Kirkland Signature",
            "KS ",
            "Organic",
            "ORG",
            "Multi-pack",
            "Variety Pack"
        ],
        "quantity_patterns": [
            "2-pack",
            "3-pack",
            "4-pack",
            "6-pack",
            "12-pack",
            "24-pack",
            "ct",
            "count",
            "oz pack",
            "lb pack"
        ],
        "price_format_hints": [
            "$/oz",
            "$/lb",
            "$/kg",
            "$/unit",
            "unit price",
            "price per"
        ],
        "common_abbreviations": {
            "ORG": "Organic",
            "KS": "Kirkland Signature",
            "LB": "Pound",
            "OZ": "Ounce",
            "CT": "Count",
            "PK": "Pack",
            "EA": "Each",
            "GAL": "Gallon",
            "QT": "Quart"
        }
    }

    # Insert Costco store with parsing profile
    # Using raw SQL with INSERT OR IGNORE for SQLite compatibility
    op.execute(
        sa.text(
            """
            INSERT OR IGNORE INTO stores (id, name, has_digital_receipts, parsing_profile)
            VALUES (:id, :name, :has_digital_receipts, :parsing_profile)
            """
        ).bindparams(
            id=COSTCO_STORE_ID,
            name="Costco",
            has_digital_receipts=False,
            parsing_profile=json.dumps(costco_profile)
        )
    )


def downgrade() -> None:
    """Remove Costco store record."""
    op.execute(
        sa.text("DELETE FROM stores WHERE id = :id").bindparams(id=COSTCO_STORE_ID)
    )
