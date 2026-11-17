"""
SourceRecipeCard.ingredient_keys: None means SQL NULL.

"NULL = ingredients unknown" is what allergy blocking and card enrichment rely
on, and enrichment finds its work with `ingredient_keys IS NULL`. A plain JSON
column stores an assigned None as the JSON value null, which that query misses.
"""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db import models
from src.db.database import Base
from src.db.models.source_catalog import SourceRecipeCard


@pytest.fixture
def db():
    _ = models  # ensure all models are registered
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _card(n: int, **fields) -> SourceRecipeCard:
    return SourceRecipeCard(
        source_type="hellofresh_web",
        external_id=f"ext{n}",
        name=f"Card {n}",
        recipe_url=f"https://www.hellofresh.com/recipes/card-{n}",
        **fields,
    )


def _unknown(db) -> set[str]:
    rows = db.query(SourceRecipeCard).filter(SourceRecipeCard.ingredient_keys.is_(None)).all()
    return {c.external_id for c in rows}


def test_is_null_finds_a_card_created_with_none(db):
    db.add_all([_card(1), _card(2, ingredient_keys=None), _card(3, ingredient_keys=[]), _card(4, ingredient_keys=["garlic"])])
    db.commit()
    assert _unknown(db) == {"ext1", "ext2"}


def test_is_null_finds_a_card_reset_to_none(db):
    card = _card(1, ingredient_keys=["garlic"])
    db.add(card)
    db.commit()
    card.ingredient_keys = None
    db.commit()
    assert _unknown(db) == {"ext1"}
    assert db.execute(text("select typeof(ingredient_keys) from source_recipe_cards")).scalar() == "null"


def test_empty_list_is_not_null(db):
    db.add(_card(1, ingredient_keys=[]))
    db.commit()
    db.expire_all()
    assert _unknown(db) == set()
    assert db.query(SourceRecipeCard).one().ingredient_keys == []
