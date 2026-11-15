"""Tests for derived catalog card tags and per-list tag filter options."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db import models
from src.db.database import Base
from src.db.models.source_catalog import SourceCollection, SourceCollectionCard, SourceRecipeCard
from src.services.card_tags import MIN_TAG_CARDS, overlap_tags, tag_cards, tag_label, tags_from_text


@pytest.fixture
def db_session():
    _ = models
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def card(name, headline=None, ingredient_keys=None):
    return SimpleNamespace(id=uuid4(), name=name, headline=headline, ingredient_keys=ingredient_keys)


class TestTagsFromText:
    def test_name_gives_main_tags_headline_gives_sides(self):
        tags = tags_from_text("Ras el Hanout Lamb & Loaded Couscous", "with Potato Wedges & a Side Salad")
        assert {"ingredient:lamb", "ingredient:couscous", "side:potatoes", "side:salad"} <= tags
        assert "dish:salads" not in tags

    def test_salad_in_the_name_is_the_dish(self):
        assert "dish:salads" in tags_from_text("Steak & Blue Cheese Salad", None)

    def test_longest_phrase_wins(self):
        tags = tags_from_text("Sweet Potato Chili con Carne", "with Green Beans")
        assert "ingredient:sweet-potato" in tags
        assert "ingredient:potatoes" not in tags
        assert "dish:chili" in tags
        assert "side:green-beans" in tags
        assert "ingredient:beans-legumes" not in tags

    def test_flavor_chili_is_not_the_dish(self):
        assert "dish:chili" not in tags_from_text("Sweet Chili Chicken", None)

    def test_plurals_match(self):
        assert "dish:tacos" in tags_from_text("Pork Carnitas Tacos", None)
        assert "ingredient:lentils" in tags_from_text("Lentils & Kale Soup", None)

    def test_labels(self):
        assert tag_label("side:salad") == "Side salad"
        assert tag_label("ingredient:chicken") == "Chicken"
        assert tag_label("ingredient:steak") == "Steak"


class TestTagCards:
    def test_offers_tags_on_enough_cards_but_not_all(self, db_session):
        cards = [
            card("Lamb Tagine", "with Couscous"),
            card("Lamb Kofta", "with Couscous"),
            card("Lamb Chops", "with Couscous"),
            card("Peanut Stew", "with Rice"),
        ]
        _, options = tag_cards(db_session, cards, "hellofresh_web", "african-recipes")
        keys = {o.key: o for o in options}
        assert keys["ingredient:lamb"].count == 3
        assert keys["side:couscous"].kind == "side"
        assert "side:rice" not in keys  # only 1 card
        assert MIN_TAG_CARDS == 3

    def test_a_tag_on_every_card_is_not_an_option(self, db_session):
        cards = [card(f"Chicken Bowl {i}") for i in range(4)]
        _, options = tag_cards(db_session, cards, "hellofresh_web", "asian-recipes")
        assert "dish:bowls" not in {o.key for o in options}

    def test_the_lists_own_value_is_dropped(self, db_session):
        cards = [card(f"Chicken Thing {i}") for i in range(3)] + [card("Tofu Thing")]
        card_tags, options = tag_cards(db_session, cards, "hellofresh_web", "chicken-recipes")
        assert "ingredient:chicken" not in {o.key for o in options}
        assert all("ingredient:chicken" not in tags for tags in card_tags.values())

    def test_mains_listed_before_sides(self, db_session):
        cards = [card("Pork Chop", "with Rice") for _ in range(3)] + [card("Fish", None)]
        _, options = tag_cards(db_session, cards, "hellofresh_web", "x")
        assert [o.kind for o in options] == ["main", "side"]

    def test_overlap_with_other_collections_tags_the_card(self, db_session):
        veg = SourceCollection(source_type="hellofresh_web", slug="vegetarian-recipes", name="Vegetarian Recipes",
                               url="https://www.hellofresh.com/recipes/vegetarian-recipes")
        db_session.add(veg)
        db_session.flush()
        stored = SourceRecipeCard(source_type="hellofresh_web", recipe_url="https://www.hellofresh.com/recipes/a-" + "a" * 24,
                                  external_id="a", name="Mystery Dish", image_url="x")
        db_session.add(stored)
        db_session.flush()
        db_session.add(SourceCollectionCard(collection_id=veg.id, card_id=stored.id, position=0))
        db_session.commit()

        card_tags, _ = tag_cards(db_session, [stored], "hellofresh_web", "italian-recipes")
        assert card_tags[stored.id] == ["diet:vegetarian"]


class TestStoredIngredientKeys:
    def test_stored_keys_produce_ingredient_tags(self, db_session):
        """A card with ingredient_keys=["broccoli"] is tagged ingredient:broccoli."""
        c = card("Mystery Bowl", ingredient_keys=["broccoli"])
        result, _ = tag_cards(db_session, [c], "hellofresh_web", "x")
        assert "ingredient:broccoli" in result[c.id]

    def test_stored_keys_override_text_derived_ingredient_tags(self, db_session):
        """When ingredient_keys is set, text-derived ingredient: tags are dropped."""
        # Name mentions chicken, but stored keys say only broccoli.
        c = card("Chicken Bowl", ingredient_keys=["broccoli"])
        result, _ = tag_cards(db_session, [c], "hellofresh_web", "x")
        assert "ingredient:broccoli" in result[c.id]
        assert "ingredient:chicken" not in result[c.id]

    def test_stored_keys_empty_list_suppresses_ingredient_tags(self, db_session):
        """ingredient_keys=[] drops text-derived ingredient: tags but keeps dish: tags."""
        c = card("Chicken Bowl", ingredient_keys=[])
        result, _ = tag_cards(db_session, [c], "hellofresh_web", "x")
        assert "ingredient:chicken" not in result[c.id]
        assert "dish:bowls" in result[c.id]

    def test_stored_keys_none_behaves_as_before(self, db_session):
        """ingredient_keys=None falls back to text-derived tags (existing behaviour)."""
        c = card("Chicken Bowl")
        result, _ = tag_cards(db_session, [c], "hellofresh_web", "x")
        assert "ingredient:chicken" in result[c.id]

    def test_tag_label_for_ingredient_key_in_vocabulary(self, db_session):
        """tag_label for a key in the ingredient vocabulary returns its display label."""
        assert tag_label("ingredient:broccoli") == "Broccoli"

    def test_tag_label_for_ingredient_key_in_recipe_themes(self, db_session):
        """tag_label for a standard recipe-themes ingredient key still works."""
        assert tag_label("ingredient:chicken") == "Chicken"

    def test_overlap_derived_ingredient_tags_dropped_when_stored_keys_present(self, db_session):
        """Overlap-derived ingredient: tags are suppressed when stored keys are set."""
        # chicken-recipes overlaps → ingredient:chicken; stored keys say only broccoli.
        chicken_coll = SourceCollection(
            source_type="hellofresh_web",
            slug="chicken-recipes",
            name="Chicken Recipes",
            url="https://www.hellofresh.com/recipes/chicken-recipes",
        )
        db_session.add(chicken_coll)
        db_session.flush()
        stored = SourceRecipeCard(
            source_type="hellofresh_web",
            external_id="overlap-stored-001",
            name="Mystery Bowl",
            recipe_url="https://www.hellofresh.com/recipes/mystery-bowl-" + "a" * 24,
            image_url="x",
        )
        stored.ingredient_keys = ["broccoli"]
        db_session.add(stored)
        db_session.flush()
        db_session.add(SourceCollectionCard(collection_id=chicken_coll.id, card_id=stored.id, position=0))
        db_session.commit()

        result, _ = tag_cards(db_session, [stored], "hellofresh_web", "x")
        assert "ingredient:broccoli" in result[stored.id]
        assert "ingredient:chicken" not in result[stored.id]


# ---------------------------------------------------------------------------
# Per-source map: non-HF source is not classified (#599)
# ---------------------------------------------------------------------------


class TestPerSourceClassification:
    def test_overlap_tags_ignores_non_hellofresh_collections(self, db_session):
        """A card sitting in a non-HF classified slug is not given overlap tags."""
        other_coll = SourceCollection(
            source_type="other_source",
            slug="vegetarian-recipes",   # would classify if source were hellofresh_web
            name="Vegetarian Recipes",
            url="https://other.example.com/recipes/vegetarian-recipes",
        )
        db_session.add(other_coll)
        db_session.flush()
        c = SourceRecipeCard(
            source_type="other_source",
            recipe_url="https://other.example.com/r-" + "a" * 24,
            external_id="oc1",
            name="Veggie Thing",
            image_url="x",
        )
        db_session.add(c)
        db_session.flush()
        db_session.add(SourceCollectionCard(collection_id=other_coll.id, card_id=c.id, position=0))
        db_session.commit()

        result = overlap_tags(db_session, [c.id])
        # No overlap tags because the collection's source is not in COLLECTION_THEMES.
        assert result.get(c.id, set()) == set()

    def test_tag_cards_no_own_key_removed_for_unknown_source(self, db_session):
        """When the collection source is not in COLLECTION_THEMES, own_key is None — no tags dropped."""
        cards = [card(f"Vegetarian Bowl {i}") for i in range(3)]
        result, _ = tag_cards(db_session, cards, "other_source", "vegetarian-recipes")
        # dish:bowls appears and is NOT suppressed (own_key would be None for unknown source)
        all_tags = {tag for tags in result.values() for tag in tags}
        assert "dish:bowls" in all_tags
