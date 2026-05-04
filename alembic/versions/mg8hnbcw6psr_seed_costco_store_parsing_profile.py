"""seed costco store parsing profile

Revision ID: mg8hnbcw6psr
Revises: lf9gmzbv5orr
Create Date: 2026-04-04 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import Table, MetaData


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

    Uses database-agnostic check-then-insert pattern for idempotency (safe to run multiple times).
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

    # Database-agnostic insert: check if store exists, then insert only if not present
    # This pattern works across SQLite, PostgreSQL, MySQL, and other databases
    # Uses check-then-insert pattern instead of database-specific upsert syntax
    connection = op.get_bind()
    metadata = MetaData()

    # Reflect the stores table from the current database schema
    stores_table = Table('stores', metadata, autoload_with=connection)

    # Use try-except to handle race condition: if multiple processes check simultaneously
    # and both try to insert, the database will reject the duplicate via unique constraint
    try:
        # Check if Costco store already exists (idempotency check)
        exists_query = sa.select(stores_table.c.id).where(stores_table.c.id == COSTCO_STORE_ID)
        result = connection.execute(exists_query).first()

        # Only insert if the store doesn't already exist (prevents duplicate key errors)
        if not result:
            insert_stmt = stores_table.insert().values(
                id=COSTCO_STORE_ID,
                name="Costco",
                name_lower="costco",
                has_digital_receipts=False,
                parsing_profile=costco_profile  # SQLAlchemy handles JSON serialization
            )
            connection.execute(insert_stmt)
    except sa.exc.IntegrityError:
        # Race condition: another process inserted between our check and insert
        # This is safe to ignore - the store exists, which is our goal
        pass


def downgrade() -> None:
    """Remove Costco store record."""
    op.execute(
        sa.text("DELETE FROM stores WHERE id = :id").bindparams(id=COSTCO_STORE_ID)
    )
