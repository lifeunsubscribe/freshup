"""update store parsing profiles phase4b

Revision ID: nh9iocxw7qtv
Revises: mg8hnbcw6psr
Create Date: 2026-04-06 16:00:00.000000

"""
from typing import Sequence, Union
import json

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'nh9iocxw7qtv'
down_revision: Union[str, None] = 'mg8hnbcw6psr'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Deterministic UUID for Generic store
GENERIC_STORE_ID = "f9e8d7c6-b5a4-4321-9876-543210fedcba"


def upgrade() -> None:
    """
    Update Costco store parsing profile and add Generic store with standardized schema.

    Standardizes parsing profiles to use consistent schema:
    - header_patterns: Store-specific header text patterns
    - abbreviations: Common abbreviations mapped to full terms
    - date_formats: Date format strings for parsing
    - category_hints: Common product category names

    Updates existing Costco store and adds new Generic fallback store.
    """
    # Updated Costco parsing profile with standardized schema
    costco_profile = {
        "header_patterns": ["COSTCO WHOLESALE", "WAREHOUSE"],
        "abbreviations": {
            "MBR": "Member",
            "QTY": "Quantity",
            "WT": "Weight",
            "EA": "Each",
            "LB": "Pound"
        },
        "date_formats": ["%m/%d/%y", "%m/%d/%Y"],
        "category_hints": ["GROCERY", "PRODUCE", "MEAT", "BAKERY", "DELI", "FROZEN"]
    }

    # Generic parsing profile for fallback/unknown stores
    generic_profile = {
        "header_patterns": [],
        "abbreviations": {
            "EA": "Each",
            "LB": "Pound",
            "OZ": "Ounce",
            "QTY": "Quantity"
        },
        "date_formats": ["%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%d/%m/%Y"],
        "category_hints": ["GROCERY", "PRODUCE", "MEAT", "DAIRY", "FROZEN", "BAKERY"]
    }

    # Update Costco store parsing profile (using name since ID may vary)
    op.execute(
        sa.text(
            """
            UPDATE stores
            SET parsing_profile = :parsing_profile
            WHERE name = :name
            """
        ).bindparams(
            name="Costco",
            parsing_profile=json.dumps(costco_profile)
        )
    )

    # Insert Generic store with parsing profile
    # Using INSERT OR IGNORE for SQLite compatibility
    op.execute(
        sa.text(
            """
            INSERT OR IGNORE INTO stores (id, name, has_digital_receipts, parsing_profile)
            VALUES (:id, :name, :has_digital_receipts, :parsing_profile)
            """
        ).bindparams(
            id=GENERIC_STORE_ID,
            name="Generic",
            has_digital_receipts=False,
            parsing_profile=json.dumps(generic_profile)
        )
    )


def downgrade() -> None:
    """
    Revert Costco parsing profile and remove Generic store.

    Note: This reverts to NULL parsing_profile for Costco rather than
    the previous schema, as the old schema is deprecated.
    """
    # Revert Costco parsing profile to NULL
    op.execute(
        sa.text(
            """
            UPDATE stores
            SET parsing_profile = NULL
            WHERE name = :name
            """
        ).bindparams(name="Costco")
    )

    # Remove Generic store
    op.execute(
        sa.text("DELETE FROM stores WHERE id = :id").bindparams(id=GENERIC_STORE_ID)
    )
