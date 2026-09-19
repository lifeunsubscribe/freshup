"""
Tests that the Alembic migration chain actually runs.

The rest of the suite builds its schema with ``Base.metadata.create_all()``,
straight from the models — migrations never execute. That is fast, but it means
a broken migration is invisible to every other test in the repo. Between
2026-05-03 and 2026-09-18 the chain had three heads and a migration that
dropped a constraint which had never existed, and all 1518 tests stayed green.

These tests close that gap. They exercise the path a real deployment takes:
an empty database upgraded to head.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from src.db.database import Base
from src.db import models  # noqa: F401  — registers models with Base.metadata


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"


def _alembic_config() -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    return cfg


def _run_alembic(*args: str, db_url: str) -> subprocess.CompletedProcess:
    """
    Run the alembic CLI in a subprocess against a specific database.

    A subprocess keeps each migration run in a clean interpreter, so module-level
    state in env.py cannot leak between tests, and it is the same entry point a
    deployment uses.
    """
    env = {**os.environ, "DATABASE_URL": db_url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def migrated_db(tmp_path):
    """An empty SQLite database upgraded to head via the alembic CLI."""
    db_path = tmp_path / "migrated.db"
    db_url = f"sqlite:///{db_path}"

    result = _run_alembic("upgrade", "head", db_url=db_url)
    assert result.returncode == 0, (
        "`alembic upgrade head` failed on an empty database.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    engine = create_engine(db_url)
    try:
        yield engine
    finally:
        engine.dispose()


class TestMigrationChainStructure:
    """Structural checks that do not need a database."""

    def test_exactly_one_head(self):
        """
        The chain must converge to a single head.

        Multiple heads make `alembic upgrade head` fail outright, which blocks
        every deployment and every subsequent migration. This is what parallel
        agent sessions produce when two of them each author a migration off the
        same parent without a merge.
        """
        script = ScriptDirectory.from_config(_alembic_config())
        heads = script.get_heads()
        assert len(heads) == 1, (
            f"Expected exactly 1 head, found {len(heads)}: {heads}. "
            "Resolve with `alembic merge -m '<reason>' <head> <head>`."
        )

    def test_no_duplicate_revision_ids(self):
        """Every migration file declares a distinct revision id."""
        script = ScriptDirectory.from_config(_alembic_config())
        revisions = [rev.revision for rev in script.walk_revisions()]
        duplicates = {r for r in revisions if revisions.count(r) > 1}
        assert not duplicates, f"Duplicate revision ids: {duplicates}"

    def test_every_revision_reachable_from_head(self):
        """
        No orphaned migrations.

        A file whose revision is not on the path from base to head never runs,
        so whatever schema change it describes silently does not happen.
        """
        script = ScriptDirectory.from_config(_alembic_config())
        head = script.get_current_head()
        reachable = {rev.revision for rev in script.iterate_revisions(head, "base")}
        all_revisions = {rev.revision for rev in script.walk_revisions()}
        orphans = all_revisions - reachable
        assert not orphans, (
            f"Migrations unreachable from head {head}: {orphans}. "
            "These will never run on a real database."
        )


class TestMigrationsRunFromEmpty:
    """The deployment path: empty database -> head."""

    def test_upgrade_head_succeeds(self, migrated_db):
        """`alembic upgrade head` completes on an empty database."""
        # The migrated_db fixture asserts returncode == 0; reaching here is the test.
        assert inspect(migrated_db).get_table_names()

    def test_migrated_schema_has_every_model_table(self, migrated_db):
        """
        Every table the models declare exists after migrating.

        This is the drift check that matters: the app queries what the models
        describe, so a table present in metadata but absent from the migrated
        database is a guaranteed runtime failure in production while tests
        (which use create_all) stay green.
        """
        migrated_tables = set(inspect(migrated_db).get_table_names())
        model_tables = set(Base.metadata.tables.keys())
        missing = model_tables - migrated_tables
        assert not missing, (
            f"Tables in the models but missing after migration: {sorted(missing)}"
        )

    def test_migrated_schema_has_every_model_column(self, migrated_db):
        """Every column the models declare exists after migrating."""
        inspector = inspect(migrated_db)
        migrated_tables = set(inspector.get_table_names())

        missing: list[str] = []
        for table_name, table in Base.metadata.tables.items():
            if table_name not in migrated_tables:
                continue  # covered by test_migrated_schema_has_every_model_table
            migrated_columns = {c["name"] for c in inspector.get_columns(table_name)}
            for column in table.columns:
                if column.name not in migrated_columns:
                    missing.append(f"{table_name}.{column.name}")

        assert not missing, (
            f"Columns in the models but missing after migration: {sorted(missing)}"
        )

    def test_renamed_rating_table_is_gone(self, migrated_db):
        """
        The Phase 2.5 rename actually took effect.

        user_recipe_ratings -> user_recipe_relations was the riskiest migration
        in the 2.5 arc and the one that was broken. Assert both directions so a
        regression cannot leave the old table behind.
        """
        tables = set(inspect(migrated_db).get_table_names())
        assert "user_recipe_relations" in tables
        assert "user_recipe_ratings" not in tables

    def test_dropped_rating_columns_are_gone(self, migrated_db):
        """is_favorite and notes were migrated into the new columns and dropped."""
        columns = {
            c["name"] for c in inspect(migrated_db).get_columns("user_recipe_relations")
        }
        assert "is_favorite" not in columns
        assert "notes" not in columns
        assert {"is_bookmarked", "is_liked", "rating_photos", "rating_comment"} <= columns


class TestMigrationRoundTrip:
    """Downgrades are rarely run, so they are where bit rot accumulates."""

    def test_downgrade_to_base_and_back(self, tmp_path):
        """
        head -> base -> head leaves a working schema.

        A downgrade that references something the upgrade never created (the
        exact bug in pj1kqfxy9rvw) fails here without touching a real database.
        """
        db_path = tmp_path / "roundtrip.db"
        db_url = f"sqlite:///{db_path}"

        up = _run_alembic("upgrade", "head", db_url=db_url)
        assert up.returncode == 0, f"initial upgrade failed:\n{up.stderr}"

        down = _run_alembic("downgrade", "base", db_url=db_url)
        assert down.returncode == 0, (
            f"`alembic downgrade base` failed:\n{down.stdout}\n{down.stderr}"
        )

        back_up = _run_alembic("upgrade", "head", db_url=db_url)
        assert back_up.returncode == 0, (
            f"re-upgrade after downgrade failed:\n{back_up.stdout}\n{back_up.stderr}"
        )

        engine = create_engine(db_url)
        try:
            tables = set(inspect(engine).get_table_names())
        finally:
            engine.dispose()

        model_tables = set(Base.metadata.tables.keys())
        assert model_tables - tables == set()


class TestNoNewSchemaDrift:
    """
    The migrated schema and the models must not drift further apart.

    Alembic's autogenerate comparison is the same machinery that would propose a
    new migration. Anything it reports is a difference between what migrations
    build and what the models declare — which is invisible to the rest of the
    suite, since those tests use create_all.

    One class of difference is knowingly tolerated: older migrations declare
    UUID columns as sa.Uuid() (CHAR(32) on SQLite) while the Phase 2.5 and
    Phase 4 migrations use sa.UUID() (NUMERIC affinity). SQLite stores both as
    TEXT and the ORM's own bind/result processors keep values correct — verified
    by round-tripping and joining across these columns — so it is cosmetic here.
    It stops being cosmetic on Postgres, so it is tracked in ADR Section 13.4 as
    a Phase 6B prerequisite rather than fixed by rewriting migration history.

    Everything else must be zero.
    """

    def test_only_known_benign_drift_remains(self, migrated_db):
        from alembic.autogenerate import compare_metadata
        from alembic.migration import MigrationContext

        with migrated_db.connect() as conn:
            diffs = compare_metadata(MigrationContext.configure(conn), Base.metadata)

        unexpected = []
        for diff in diffs:
            # compare_metadata yields column-level diffs as a list of tuples and
            # table-level diffs as a bare tuple.
            entries = diff if isinstance(diff, list) else [diff]
            for entry in entries:
                if not isinstance(entry, tuple) or not entry:
                    unexpected.append(entry)
                    continue
                if entry[0] == "modify_type" and _is_uuid_affinity_diff(entry):
                    continue
                unexpected.append(entry)

        assert not unexpected, (
            "New drift between the migrated schema and the models:\n  "
            + "\n  ".join(repr(u) for u in unexpected)
            + "\n\nEither add the change to a migration, or declare it on the model "
            "(ADR Section 13, rule 5: model and migration move together)."
        )


def _is_uuid_affinity_diff(entry: tuple) -> bool:
    """True for the documented sa.UUID() vs sa.Uuid() declaration mismatch."""
    if len(entry) < 7:
        return False
    existing_type, target_type = entry[5], entry[6]
    rendered = {type(existing_type).__name__, type(target_type).__name__}
    return rendered <= {"NUMERIC", "Uuid", "UUID", "CHAR"}
