"""
Tests for Alembic migrations, particularly database-agnostic patterns.
"""
import ast
import json
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.database import Base
from src.db import models  # noqa: F401  — registers models with Base.metadata


TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def db_session():
    """Create a fresh in-memory database with all tables via model metadata."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


COSTCO_STORE_ID = "a1b2c3d4-e5f6-4789-0abc-def123456789"


def _run_seed_insert(conn):
    """Execute the same check-then-insert logic the migration uses."""
    from sqlalchemy import MetaData, Table
    import sqlalchemy as sa

    metadata = MetaData()
    stores_table = Table("stores", metadata, autoload_with=conn)
    exists_query = sa.select(stores_table.c.id).where(
        stores_table.c.id == COSTCO_STORE_ID
    )
    result = conn.execute(exists_query).first()
    if not result:
        costco_profile = {
            "item_name_patterns": [
                "Kirkland Signature", "KS ", "Organic", "ORG",
                "Multi-pack", "Variety Pack",
            ],
            "quantity_patterns": [
                "2-pack", "3-pack", "4-pack", "6-pack", "12-pack",
                "24-pack", "ct", "count", "oz pack", "lb pack",
            ],
            "price_format_hints": [
                "$/oz", "$/lb", "$/kg", "$/unit", "unit price", "price per",
            ],
            "common_abbreviations": {
                "ORG": "Organic", "KS": "Kirkland Signature",
                "LB": "Pound", "OZ": "Ounce", "CT": "Count",
                "PK": "Pack", "EA": "Each", "GAL": "Gallon", "QT": "Quart",
            },
        }
        conn.execute(
            stores_table.insert().values(
                id=COSTCO_STORE_ID,
                name="Costco",
                has_digital_receipts=False,
                parsing_profile=costco_profile,
            )
        )
        conn.commit()


def test_costco_store_migration_idempotency(db_session):
    """
    Verify the check-then-insert seed logic is idempotent:
    running twice produces exactly one Costco row.
    """
    conn = db_session.get_bind().connect()

    # First insert
    _run_seed_insert(conn)

    row = conn.execute(
        text("SELECT id, name, has_digital_receipts, parsing_profile "
             "FROM stores WHERE id = :id"),
        {"id": COSTCO_STORE_ID},
    ).first()

    assert row is not None, "Costco store should be inserted"
    assert row.name == "Costco"
    assert row.has_digital_receipts == False  # noqa: E712

    parsing_profile = row.parsing_profile
    if isinstance(parsing_profile, str):
        parsing_profile = json.loads(parsing_profile)
    assert "item_name_patterns" in parsing_profile
    assert "Kirkland Signature" in parsing_profile["item_name_patterns"]

    # Second insert — idempotency check
    _run_seed_insert(conn)

    count = conn.execute(
        text("SELECT COUNT(*) FROM stores WHERE id = :id"),
        {"id": COSTCO_STORE_ID},
    ).scalar()
    assert count == 1, "Idempotent insert should not duplicate the row"

    conn.close()


def test_migration_uses_database_agnostic_syntax():
    """
    Static check: the migration file must not contain database-specific
    upsert syntax in executable code.
    """
    migration_path = (
        "alembic/versions/mg8hnbcw6psr_seed_costco_store_parsing_profile.py"
    )
    with open(migration_path, "r") as f:
        source = f.read()

    # Parse the AST to extract only string literals and executable code,
    # ignoring comments and docstrings.
    tree = ast.parse(source)

    # Collect all string literals that appear in expressions (e.g., op.execute(text("...")))
    # but skip module/function/class docstrings.
    code_strings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            # This is a standalone string expression (docstring) — skip it
            continue
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            code_strings.append(node.value)

    code_text = " ".join(code_strings)

    db_specific_patterns = [
        "INSERT OR IGNORE",   # SQLite
        "INSERT IGNORE",      # MySQL
        "ON CONFLICT DO NOTHING",  # PostgreSQL
    ]
    for pattern in db_specific_patterns:
        assert pattern not in code_text, (
            f"Migration executable code should not contain '{pattern}'"
        )

    # Verify database-agnostic patterns ARE present in the source
    assert "Table" in source, "Should use SQLAlchemy Table construct"
    assert "MetaData" in source, "Should use SQLAlchemy MetaData"
    assert "if not result:" in source, (
        "Should use check-then-insert pattern for idempotency"
    )
