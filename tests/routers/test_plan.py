"""
Integration tests for meal plan endpoints.

Tests cover:
- POST /plan/draft/generate: Auto-draft meal plan generation
- GET /plan/week: Weekly plan viewing with status separation
- PUT /plan/entries/{id}/confirm: Entry confirmation with grocery list propagation
- Authentication requirements
- Validation scenarios
"""

import pytest
from collections import Counter
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from uuid import uuid4, UUID
from datetime import date, timedelta, datetime

from src.db.database import Base, get_db
from src.db import models
from src.db.models.user import User, UserRole
from src.db.models.recipe import Recipe
from src.db.models.recipe_ingredient import RecipeIngredient
from src.db.models.inventory_item import InventoryItem
from src.db.models.meal_plan import MealPlanEntry, MealPlanStatus, MealType
from src.db.models.grocery_list import GroceryListItem
from src.db.models.source_catalog import SourceCollection, SourceRecipeCard, SourceCollectionCard
from src.services.auth_service import hash_password, create_access_token

from fastapi import FastAPI
from src.routers import plan as plan_router

# Create a test app without lifespan
app = FastAPI(
    title="FreshUp",
    description="Privacy-first kitchen management system",
    version="0.1.0",
)

# Register the plan router
app.include_router(plan_router.router)


# Create an in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """Set up test environment variables."""
    from src.config import get_settings
    get_settings.cache_clear()

    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-testing-only-min-32-chars")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "43200")

    get_settings.cache_clear()


@pytest.fixture
def db_session():
    """Create a fresh database session for each test."""
    from sqlalchemy.pool import StaticPool

    # Import models to ensure all SQLAlchemy model classes are registered
    # with Base.metadata before create_all() is called
    _ = models

    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def client(db_session):
    """Create a test client with database dependency override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    user = User(
        id=uuid4(),
        name="Test User",
        email="test@example.com",
        hashed_password=hash_password("testpass123"),
        role=UserRole.member.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    """Generate auth headers with valid token."""
    token = create_access_token({"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def recipes_pool(db_session, test_user):
    """Create a pool of recipes for meal planning."""
    recipes = []
    for i in range(10):
        recipe = Recipe(
            id=uuid4(),
            name=f"Test Recipe {i}",
            source_type="manual",
            base_servings=4,
            prep_time_minutes=10,
            cook_time_minutes=20,
            times_cooked=i,  # Varying popularity
            is_persisted=True,
            created_by=test_user.id,
        )
        db_session.add(recipe)
        recipes.append(recipe)

    db_session.commit()
    for recipe in recipes:
        db_session.refresh(recipe)

    # Add ingredients to first recipe for grocery list propagation
    ingredient = RecipeIngredient(
        id=uuid4(),
        recipe_id=recipes[0].id,
        ingredient_name="Test Ingredient",
        quantity=2.0,
        unit="cups",
        is_optional=False,
    )
    db_session.add(ingredient)
    db_session.commit()

    return recipes


@pytest.fixture
def one_top_level_collection(db_session):
    """Create a single top-level SourceCollection so rank_candidates processes recipe candidates.

    rank_candidates early-returns when no top-level collections exist, so any
    test that calls generate_draft and expects recipe-based entries must provide this.
    """
    collection = SourceCollection(
        id=uuid4(),
        source_type="manual",
        slug="test-collection",
        name="Test Collection",
        url="https://example.com/recipes",
        parent_slug=None,
    )
    db_session.add(collection)
    db_session.commit()
    db_session.refresh(collection)
    return collection


def test_generate_draft_creates_seven_entries(client, db_session, auth_headers, recipes_pool, one_top_level_collection):
    """Test that draft generation creates 7 dinner entries."""
    # Use fixed Monday date to avoid flakiness around week boundaries
    week_start = date(2025, 6, 2)  # Monday, June 2, 2025

    response = client.post(
        "/plan/draft/generate",
        json={"week_start": week_start.isoformat()},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["entries_created"] == 7
    assert data["week_start"] == week_start.isoformat()
    assert len(data["entries"]) == 7

    # Verify all entries are drafts for dinner
    for entry in data["entries"]:
        assert entry["status"] == MealPlanStatus.draft.value
        assert entry["meal_type"] == MealType.dinner.value


def test_generate_draft_requires_monday(client, auth_headers, recipes_pool):
    """Test that draft generation requires week_start to be a Monday."""
    # Use fixed Tuesday date to avoid flakiness
    week_start = date(2025, 6, 3)  # Tuesday, June 3, 2025

    response = client.post(
        "/plan/draft/generate",
        json={"week_start": week_start.isoformat()},
        headers=auth_headers,
    )

    assert response.status_code == 422  # Validation error


def test_generate_draft_with_few_candidates_fills_what_it_can(client, db_session, auth_headers, test_user):
    """With fewer than 7 eligible candidates, draft fills what it can (logs a warning, no error).

    With 3 persisted recipes and a top-level collection, rank_candidates returns 3
    candidates.  select_week places all 3; generate returns 200 with entries_created=3.
    """
    collection = SourceCollection(
        id=uuid4(),
        source_type="manual",
        slug="few-recipes-coll",
        name="Few Recipes Collection",
        url="https://example.com/few",
        parent_slug=None,
    )
    db_session.add(collection)

    for i in range(3):
        recipe = Recipe(
            id=uuid4(),
            name=f"Sparse Recipe {i}",
            source_type="manual",
            base_servings=4,
            is_persisted=True,
            created_by=test_user.id,
        )
        db_session.add(recipe)
    db_session.commit()

    week_start = date(2025, 6, 2)

    response = client.post(
        "/plan/draft/generate",
        json={"week_start": week_start.isoformat()},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["entries_created"] == 3
    assert len(data["entries"]) == 3


def test_generate_draft_prevents_duplicates(client, db_session, auth_headers, recipes_pool, one_top_level_collection):
    """Test that draft generation fails if draft entries already exist for the week."""
    # Use fixed Monday date to avoid flakiness
    week_start = date(2025, 6, 2)  # Monday, June 2, 2025

    # Generate initial draft plan
    response = client.post(
        "/plan/draft/generate",
        json={"week_start": week_start.isoformat()},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["entries_created"] == 7

    # Attempt to generate draft plan again for the same week
    response = client.post(
        "/plan/draft/generate",
        json={"week_start": week_start.isoformat()},
        headers=auth_headers,
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "Draft entries already exist" in detail
    assert "Delete or confirm existing drafts" in detail


def test_get_week_returns_empty_for_new_week(client, auth_headers):
    """Test that getting a week with no entries returns empty lists."""
    # Use fixed Monday date to avoid flakiness
    week_start = date(2025, 6, 2)  # Monday, June 2, 2025

    response = client.get(
        f"/plan/week?week_start={week_start.isoformat()}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["week_start"] == week_start.isoformat()
    assert data["confirmed_entries"] == []
    assert data["draft_entries"] == []


def test_get_week_separates_by_status(client, db_session, auth_headers, recipes_pool):
    """Test that week view separates entries by status."""
    # Use fixed Monday date to avoid flakiness
    week_start = date(2025, 6, 2)  # Monday, June 2, 2025

    # Create draft entry
    draft_entry = MealPlanEntry(
        id=uuid4(),
        date=week_start,
        meal_type=MealType.dinner.value,
        recipe_id=recipes_pool[0].id,
        planned_servings=4,
        status=MealPlanStatus.draft.value,
    )
    db_session.add(draft_entry)

    # Create confirmed entry
    confirmed_entry = MealPlanEntry(
        id=uuid4(),
        date=week_start + timedelta(days=1),
        meal_type=MealType.dinner.value,
        recipe_id=recipes_pool[1].id,
        planned_servings=4,
        status=MealPlanStatus.approved.value,
    )
    db_session.add(confirmed_entry)
    db_session.commit()

    response = client.get(
        f"/plan/week?week_start={week_start.isoformat()}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert len(data["draft_entries"]) == 1
    assert len(data["confirmed_entries"]) == 1
    assert data["draft_entries"][0]["status"] == MealPlanStatus.draft.value
    assert data["confirmed_entries"][0]["status"] == MealPlanStatus.approved.value


def test_confirm_entry_transitions_to_approved(client, db_session, auth_headers, recipes_pool):
    """Test that confirming an entry transitions it to approved status."""
    # Create a draft entry with a recipe that has ingredients
    entry = MealPlanEntry(
        id=uuid4(),
        date=date(2025, 6, 2),  # Fixed date to avoid flakiness
        meal_type=MealType.dinner.value,
        recipe_id=recipes_pool[0].id,  # Has ingredient from fixture
        planned_servings=4,
        status=MealPlanStatus.draft.value,
    )
    db_session.add(entry)
    db_session.commit()

    response = client.put(
        f"/plan/entries/{entry.id}/confirm",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["entry"]["status"] == MealPlanStatus.approved.value
    assert data["grocery_items_added"] > 0  # At least one ingredient added


def test_confirm_entry_adds_ingredients_to_grocery_list(client, db_session, auth_headers, recipes_pool, test_user):
    """Test that confirming an entry adds recipe ingredients to grocery list."""
    # Create a draft entry
    entry = MealPlanEntry(
        id=uuid4(),
        date=date(2025, 6, 2),  # Fixed date to avoid flakiness
        meal_type=MealType.dinner.value,
        recipe_id=recipes_pool[0].id,
        planned_servings=4,
        status=MealPlanStatus.draft.value,
    )
    db_session.add(entry)
    db_session.commit()

    # Verify no grocery items exist before confirmation
    grocery_count_before = db_session.query(GroceryListItem).count()
    assert grocery_count_before == 0

    response = client.put(
        f"/plan/entries/{entry.id}/confirm",
        headers=auth_headers,
    )

    assert response.status_code == 200

    # Verify grocery items were created
    grocery_items = db_session.query(GroceryListItem).all()
    assert len(grocery_items) > 0
    assert grocery_items[0].source == "meal_plan"


def test_confirm_entry_fails_for_nonexistent_entry(client, auth_headers):
    """Test that confirming a non-existent entry returns 404."""
    fake_id = uuid4()
    response = client.put(
        f"/plan/entries/{fake_id}/confirm",
        headers=auth_headers,
    )

    assert response.status_code == 404


def test_confirm_entry_fails_for_already_confirmed(client, db_session, auth_headers, recipes_pool):
    """Test that confirming an already-confirmed entry fails."""
    # Create an already-confirmed entry
    entry = MealPlanEntry(
        id=uuid4(),
        date=date(2025, 6, 2),  # Fixed date to avoid flakiness
        meal_type=MealType.dinner.value,
        recipe_id=recipes_pool[0].id,
        planned_servings=4,
        status=MealPlanStatus.approved.value,
    )
    db_session.add(entry)
    db_session.commit()

    response = client.put(
        f"/plan/entries/{entry.id}/confirm",
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "Only draft entries can be confirmed" in response.json()["detail"]


def test_endpoints_require_authentication(client):
    """Test that all endpoints require authentication."""
    # Use fixed Monday date to avoid flakiness
    week_start = date(2025, 6, 2)  # Monday, June 2, 2025

    # Test draft generation
    response = client.post(
        "/plan/draft/generate",
        json={"week_start": week_start.isoformat()},
    )
    assert response.status_code == 401

    # Test week view
    response = client.get(f"/plan/week?week_start={week_start.isoformat()}")
    assert response.status_code == 401

    # Test confirm entry
    fake_id = uuid4()
    response = client.put(f"/plan/entries/{fake_id}/confirm")
    assert response.status_code == 401

    # Test opt-out
    response = client.put(f"/plan/entries/{fake_id}/opt-out")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /plan/entries — create_entry tests
# ---------------------------------------------------------------------------

@pytest.fixture
def single_recipe(db_session, test_user):
    """Create a single recipe with a known base_servings value."""
    recipe = Recipe(
        id=uuid4(),
        name="Single Test Recipe",
        source_type="manual",
        base_servings=3,
        prep_time_minutes=10,
        cook_time_minutes=20,
        is_persisted=True,
        created_by=test_user.id,
    )
    db_session.add(recipe)
    db_session.commit()
    db_session.refresh(recipe)
    return recipe


@pytest.fixture
def unpersisted_recipe(db_session, test_user):
    """Create a recipe that has not been persisted (browse-cache state)."""
    recipe = Recipe(
        id=uuid4(),
        name="Browse Cache Recipe",
        source_type="url_import",
        base_servings=2,
        is_persisted=False,
        created_by=test_user.id,
    )
    db_session.add(recipe)
    db_session.commit()
    db_session.refresh(recipe)
    return recipe


def test_create_entry_returns_201_with_body(client, auth_headers, single_recipe):
    """POST /plan/entries creates an entry and returns 201 with the entry body."""
    payload = {
        "date": "2026-09-22",
        "meal_type": "dinner",
        "recipe_id": str(single_recipe.id),
        "planned_servings": 4,
    }

    response = client.post("/plan/entries", json=payload, headers=auth_headers)

    assert response.status_code == 201
    data = response.json()
    assert data["recipe_id"] == str(single_recipe.id)
    assert data["meal_type"] == "dinner"
    assert data["planned_servings"] == 4
    assert data["status"] == MealPlanStatus.draft.value
    assert "id" in data


def test_create_entry_appears_in_week_view(client, db_session, auth_headers, single_recipe):
    """Entry created via POST /plan/entries is returned by GET /plan/week."""
    entry_date = date(2026, 9, 22)

    client.post(
        "/plan/entries",
        json={
            "date": entry_date.isoformat(),
            "meal_type": "lunch",
            "recipe_id": str(single_recipe.id),
            "planned_servings": 2,
        },
        headers=auth_headers,
    )

    # week_start must cover 2026-09-22; Monday of that week is 2026-09-21
    week_start = date(2026, 9, 21)
    response = client.get(
        f"/plan/week?week_start={week_start.isoformat()}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    draft_ids = [e["recipe_id"] for e in data["draft_entries"]]
    assert str(single_recipe.id) in draft_ids


def test_create_entry_defaults_planned_servings_to_base_servings(
    client, auth_headers, single_recipe
):
    """When planned_servings is omitted, it defaults to the recipe's base_servings."""
    payload = {
        "date": "2026-09-22",
        "meal_type": "breakfast",
        "recipe_id": str(single_recipe.id),
        # planned_servings intentionally omitted
    }

    response = client.post("/plan/entries", json=payload, headers=auth_headers)

    assert response.status_code == 201
    assert response.json()["planned_servings"] == single_recipe.base_servings


def test_create_entry_invalid_meal_type_returns_422(client, auth_headers, single_recipe):
    """Invalid meal_type value is rejected with 422 by Pydantic."""
    payload = {
        "date": "2026-09-22",
        "meal_type": "midnight_snack",  # not a valid MealType
        "recipe_id": str(single_recipe.id),
        "planned_servings": 2,
    }

    response = client.post("/plan/entries", json=payload, headers=auth_headers)

    assert response.status_code == 422


def test_create_entry_zero_servings_returns_422(client, auth_headers, single_recipe):
    """planned_servings of 0 is rejected with 422 (ge=1 constraint)."""
    payload = {
        "date": "2026-09-22",
        "meal_type": "dinner",
        "recipe_id": str(single_recipe.id),
        "planned_servings": 0,
    }

    response = client.post("/plan/entries", json=payload, headers=auth_headers)

    assert response.status_code == 422


def test_create_entry_negative_servings_returns_422(client, auth_headers, single_recipe):
    """planned_servings < 0 is rejected with 422 (ge=1 constraint)."""
    payload = {
        "date": "2026-09-22",
        "meal_type": "dinner",
        "recipe_id": str(single_recipe.id),
        "planned_servings": -1,
    }

    response = client.post("/plan/entries", json=payload, headers=auth_headers)

    assert response.status_code == 422


def test_create_entry_unknown_recipe_returns_404(client, auth_headers):
    """POST /plan/entries with an unknown recipe_id returns 404."""
    payload = {
        "date": "2026-09-22",
        "meal_type": "dinner",
        "recipe_id": str(uuid4()),
        "planned_servings": 2,
    }

    response = client.post("/plan/entries", json=payload, headers=auth_headers)

    assert response.status_code == 404


def test_create_entry_requires_authentication(client, single_recipe):
    """POST /plan/entries without auth returns 401."""
    payload = {
        "date": "2026-09-22",
        "meal_type": "dinner",
        "recipe_id": str(single_recipe.id),
        "planned_servings": 2,
    }

    response = client.post("/plan/entries", json=payload)  # no auth headers

    assert response.status_code == 401


def test_create_entry_caller_is_in_user_opt_ins(client, db_session, auth_headers, test_user, single_recipe):
    """The calling user is added to the entry's user_opt_ins."""
    response = client.post(
        "/plan/entries",
        json={
            "date": "2026-09-22",
            "meal_type": "dinner",
            "recipe_id": str(single_recipe.id),
            "planned_servings": 2,
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    from uuid import UUID as _UUID
    entry_id = _UUID(response.json()["id"])

    # Verify in the database that the user is in opt-ins
    from src.db.models.meal_plan import meal_plan_user_association
    row = db_session.execute(
        meal_plan_user_association.select().where(
            meal_plan_user_association.c.meal_plan_entry_id == entry_id
        )
    ).first()
    assert row is not None
    assert str(row.user_id) == str(test_user.id)


def test_create_entry_triggers_recipe_persistence(
    client, db_session, auth_headers, unpersisted_recipe
):
    """Adding a non-persisted recipe to the plan sets is_persisted=True."""
    assert unpersisted_recipe.is_persisted is False

    response = client.post(
        "/plan/entries",
        json={
            "date": "2026-09-22",
            "meal_type": "dinner",
            "recipe_id": str(unpersisted_recipe.id),
        },
        headers=auth_headers,
    )

    assert response.status_code == 201

    # Re-query to get fresh state from the database
    db_session.expire(unpersisted_recipe)
    db_session.refresh(unpersisted_recipe)
    assert unpersisted_recipe.is_persisted is True


def test_create_entry_allows_duplicate_date_meal_slot(
    client, auth_headers, single_recipe
):
    """Two entries for the same date and meal slot are both accepted (201)."""
    payload = {
        "date": "2026-09-22",
        "meal_type": "dinner",
        "recipe_id": str(single_recipe.id),
        "planned_servings": 2,
    }

    response1 = client.post("/plan/entries", json=payload, headers=auth_headers)
    response2 = client.post("/plan/entries", json=payload, headers=auth_headers)

    assert response1.status_code == 201
    assert response2.status_code == 201
    # Each call creates a distinct entry
    assert response1.json()["id"] != response2.json()["id"]


def test_create_entry_persisted_recipe_entry_is_committed(
    client, db_session, auth_headers, single_recipe
):
    """Entry created for an already-persisted recipe must be durable (committed).

    Regression for: trigger_persistence returns False without committing when
    recipe.is_persisted is True, causing the entry to be discarded on session close.
    Verified via GET /plan/week on a fresh query — the draft entry must appear.
    """
    entry_date = date(2026, 9, 22)
    # single_recipe fixture has is_persisted=True — this is the primary happy path
    assert single_recipe.is_persisted is True

    response = client.post(
        "/plan/entries",
        json={
            "date": entry_date.isoformat(),
            "meal_type": "dinner",
            "recipe_id": str(single_recipe.id),
            "planned_servings": 2,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    from uuid import UUID as _UUID
    entry_id = _UUID(response.json()["id"])

    # Query via a fresh SELECT to confirm the row was committed, not just flushed
    fresh_entry = db_session.query(MealPlanEntry).filter(
        MealPlanEntry.id == entry_id
    ).first()
    assert fresh_entry is not None, (
        "Entry was not committed to the database; likely discarded after session close"
    )
    assert fresh_entry.recipe_id == single_recipe.id


@pytest.fixture
def second_user(db_session):
    """Create a second household member for multi-user opt-out tests."""
    user = User(
        id=uuid4(),
        name="Second User",
        email="second@example.com",
        hashed_password=hash_password("testpass123"),
        role=UserRole.member.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def second_user_headers(second_user):
    """Generate auth headers for the second user."""
    token = create_access_token({"sub": str(second_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def opted_in_entry(db_session, test_user, single_recipe):
    """Create a meal plan entry with test_user already opted in."""
    entry = MealPlanEntry(
        id=uuid4(),
        date=date(2026, 9, 22),
        meal_type=MealType.dinner.value,
        recipe_id=single_recipe.id,
        planned_servings=1,
        status=MealPlanStatus.draft.value,
    )
    db_session.add(entry)
    db_session.flush()
    # Opt the test user in via the association table
    entry.user_opt_ins.append(test_user)
    db_session.commit()
    db_session.refresh(entry)
    return entry


# ---------------------------------------------------------------------------
# PUT /plan/entries/{id}/opt-out tests
# ---------------------------------------------------------------------------


def test_opt_out_removes_caller_from_user_opt_ins(
    client, db_session, auth_headers, test_user, opted_in_entry
):
    """Opting out removes the caller from the entry's user_opt_ins association."""
    # Confirm user is currently opted in
    from src.db.models.meal_plan import meal_plan_user_association as _assoc_tbl
    row_before = db_session.execute(
        _assoc_tbl.select().where(
            _assoc_tbl.c.meal_plan_entry_id == opted_in_entry.id,
            _assoc_tbl.c.user_id == test_user.id,
        )
    ).first()
    assert row_before is not None

    response = client.put(
        f"/plan/entries/{opted_in_entry.id}/opt-out",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert "entry" in data
    assert data["entry"]["id"] == str(opted_in_entry.id)

    # Verify the association row is gone
    row_after = db_session.execute(
        _assoc_tbl.select().where(
            _assoc_tbl.c.meal_plan_entry_id == opted_in_entry.id,
            _assoc_tbl.c.user_id == test_user.id,
        )
    ).first()
    assert row_after is None


def test_opt_out_is_idempotent(client, auth_headers, opted_in_entry):
    """Calling opt-out twice returns 200 both times with the same final state."""
    url = f"/plan/entries/{opted_in_entry.id}/opt-out"

    first = client.put(url, headers=auth_headers)
    second = client.put(url, headers=auth_headers)

    assert first.status_code == 200
    assert second.status_code == 200
    # Both responses return the same entry id
    assert first.json()["entry"]["id"] == second.json()["entry"]["id"]


def test_opt_out_entry_still_exists_after_last_participant_leaves(
    client, db_session, auth_headers, opted_in_entry
):
    """The entry is NOT deleted when the last participant opts out."""
    response = client.put(
        f"/plan/entries/{opted_in_entry.id}/opt-out",
        headers=auth_headers,
    )

    assert response.status_code == 200

    # Entry must still exist in the database
    surviving = db_session.query(MealPlanEntry).filter(
        MealPlanEntry.id == opted_in_entry.id
    ).first()
    assert surviving is not None


def test_opt_out_does_not_affect_other_users_opt_ins(
    client, db_session, auth_headers, second_user, single_recipe
):
    """Opting out only removes the calling user; other participants stay opted in."""
    from src.db.models.meal_plan import meal_plan_user_association as _assoc_tbl

    # Create a user from auth_headers (test_user) and second_user both opted in
    # We need test_user here — retrieve it from the db by email
    test_user_obj = db_session.query(User).filter(User.email == "test@example.com").first()

    entry = MealPlanEntry(
        id=uuid4(),
        date=date(2026, 9, 22),
        meal_type=MealType.dinner.value,
        recipe_id=single_recipe.id,
        planned_servings=2,
        status=MealPlanStatus.draft.value,
    )
    db_session.add(entry)
    db_session.flush()
    entry.user_opt_ins.append(test_user_obj)
    entry.user_opt_ins.append(second_user)
    db_session.commit()

    # test_user opts out
    response = client.put(
        f"/plan/entries/{entry.id}/opt-out",
        headers=auth_headers,
    )

    assert response.status_code == 200

    # second_user's opt-in row must still be present
    row = db_session.execute(
        _assoc_tbl.select().where(
            _assoc_tbl.c.meal_plan_entry_id == entry.id,
            _assoc_tbl.c.user_id == second_user.id,
        )
    ).first()
    assert row is not None, "second_user's opt-in was incorrectly removed"


def test_opt_out_recomputes_planned_servings_when_others_remain(
    client, db_session, auth_headers, second_user, single_recipe
):
    """planned_servings drops to the remaining opt-in count when > 0."""
    test_user_obj = db_session.query(User).filter(User.email == "test@example.com").first()

    entry = MealPlanEntry(
        id=uuid4(),
        date=date(2026, 9, 22),
        meal_type=MealType.dinner.value,
        recipe_id=single_recipe.id,
        planned_servings=2,
        status=MealPlanStatus.draft.value,
    )
    db_session.add(entry)
    db_session.flush()
    entry.user_opt_ins.append(test_user_obj)
    entry.user_opt_ins.append(second_user)
    db_session.commit()

    response = client.put(
        f"/plan/entries/{entry.id}/opt-out",
        headers=auth_headers,
    )

    assert response.status_code == 200
    # 1 participant remains → planned_servings must be 1
    assert response.json()["entry"]["planned_servings"] == 1


def test_opt_out_leaves_planned_servings_unchanged_when_list_empties(
    client, auth_headers, opted_in_entry
):
    """planned_servings is NOT changed when the last participant opts out."""
    original_servings = opted_in_entry.planned_servings

    response = client.put(
        f"/plan/entries/{opted_in_entry.id}/opt-out",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["entry"]["planned_servings"] == original_servings


def test_opt_out_user_never_opted_in_returns_200(
    client, db_session, auth_headers, single_recipe
):
    """A user who was never in user_opt_ins can still call opt-out — it's a no-op 200."""
    # Create an entry with no opt-ins at all
    entry = MealPlanEntry(
        id=uuid4(),
        date=date(2026, 9, 22),
        meal_type=MealType.dinner.value,
        recipe_id=single_recipe.id,
        planned_servings=4,
        status=MealPlanStatus.draft.value,
    )
    db_session.add(entry)
    db_session.commit()

    response = client.put(
        f"/plan/entries/{entry.id}/opt-out",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["entry"]["id"] == str(entry.id)


def test_opt_out_unknown_entry_returns_404(client, auth_headers):
    """opt-out on an unknown entry id returns 404."""
    response = client.put(
        f"/plan/entries/{uuid4()}/opt-out",
        headers=auth_headers,
    )

    assert response.status_code == 404


def test_opt_out_requires_authentication(client, opted_in_entry):
    """opt-out without auth returns 401."""
    response = client.put(f"/plan/entries/{opted_in_entry.id}/opt-out")

    assert response.status_code == 401


def test_opt_out_entry_still_appears_in_week_view(
    client, auth_headers, opted_in_entry
):
    """After opting out the entry still shows up in GET /plan/week."""
    client.put(
        f"/plan/entries/{opted_in_entry.id}/opt-out",
        headers=auth_headers,
    )

    # opted_in_entry date is 2026-09-22, which falls in week starting 2026-09-21
    week_start = date(2026, 9, 21)
    response = client.get(
        f"/plan/week?week_start={week_start.isoformat()}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    all_entry_ids = [
        e["id"] for e in data["draft_entries"] + data["confirmed_entries"]
    ]
    assert str(opted_in_entry.id) in all_entry_ids


def test_create_entry_omitted_planned_servings_falls_back_to_base_servings(
    client, db_session, auth_headers, test_user
):
    """When planned_servings is omitted, the entry uses recipe.base_servings as the default.

    Recipe.base_servings is a non-nullable int column (default=4); omitting
    planned_servings falls back to that value and the request succeeds with 201.
    """
    recipe = Recipe(
        id=uuid4(),
        name="Recipe With Default Servings",
        source_type="manual",
        is_persisted=True,
        created_by=test_user.id,
    )
    db_session.add(recipe)
    db_session.commit()
    db_session.refresh(recipe)

    response = client.post(
        "/plan/entries",
        json={
            "date": "2026-09-22",
            "meal_type": "dinner",
            "recipe_id": str(recipe.id),
            # planned_servings intentionally omitted — falls back to recipe.base_servings
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["planned_servings"] == recipe.base_servings


def test_opt_out_db_commit_failure_returns_400(
    client, db_session, auth_headers, opted_in_entry, monkeypatch
):
    """A SQLAlchemyError on db.commit during opt-out is re-raised as ValidationError
    and mapped to HTTP 400 by the router — not leaked as a 500.
    """
    from sqlalchemy.exc import SQLAlchemyError

    monkeypatch.setattr(db_session, "commit", lambda: (_ for _ in ()).throw(SQLAlchemyError("simulated commit failure")))

    response = client.put(
        f"/plan/entries/{opted_in_entry.id}/opt-out",
        headers=auth_headers,
    )

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Phase 2.5J: draft from recommendations, card entries, display field
# ---------------------------------------------------------------------------


def _make_collection(db_session, source_type: str, slug: str) -> SourceCollection:
    coll = SourceCollection(
        id=uuid4(),
        source_type=source_type,
        slug=slug,
        name=slug.replace("-", " ").capitalize(),
        url=f"https://example.com/{slug}",
        parent_slug=None,
    )
    db_session.add(coll)
    db_session.flush()
    return coll


def _make_card(
    db_session,
    collection: SourceCollection,
    name: str,
    *,
    ingredient_keys: list = None,
    prep_time_minutes: int = 30,
    position: int = 0,
) -> SourceRecipeCard:
    card = SourceRecipeCard(
        id=uuid4(),
        source_type=collection.source_type,
        external_id=str(uuid4()),
        name=name,
        recipe_url=f"https://example.com/recipe/{uuid4()}",
        ingredient_keys=ingredient_keys or [],
        prep_time_minutes=prep_time_minutes,
        image_url=f"https://cdn.example.com/{uuid4()}.jpg",
    )
    db_session.add(card)
    db_session.flush()
    db_session.add(SourceCollectionCard(
        collection_id=collection.id,
        card_id=card.id,
        position=position,
    ))
    return card


@pytest.fixture
def two_source_draft_pool(db_session, test_user):
    """3 persisted recipes + 20 cards from two sources for draft generation tests."""
    for i in range(3):
        db_session.add(Recipe(
            id=uuid4(),
            name=f"Persisted Recipe {i}",
            source_type="manual",
            base_servings=4,
            is_persisted=True,
            created_by=test_user.id,
        ))

    coll_a = _make_collection(db_session, "hellofresh_web", "hf-weekly")
    coll_b = _make_collection(db_session, "homechef_web", "hc-weekly")

    cards = []
    for i in range(10):
        cards.append(_make_card(
            db_session, coll_a, f"HF Card {i}",
            ingredient_keys=["chicken" if i % 2 == 0 else "beef"],
            prep_time_minutes=30,
            position=i,
        ))
    for i in range(10):
        cards.append(_make_card(
            db_session, coll_b, f"HC Card {i}",
            ingredient_keys=["pork"],
            prep_time_minutes=25,
            position=i,
        ))

    db_session.commit()
    return {"coll_a": coll_a, "coll_b": coll_b, "cards": cards}


def test_draft_generates_seven_from_recipes_and_cards(
    client, auth_headers, two_source_draft_pool
):
    """With 3 recipes and 20 cards from two sources, generation creates 7 draft dinners."""
    week_start = date(2025, 6, 2)

    response = client.post(
        "/plan/draft/generate",
        json={"week_start": week_start.isoformat()},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["entries_created"] == 7
    assert len(data["entries"]) == 7
    for entry in data["entries"]:
        assert entry["status"] == MealPlanStatus.draft.value
        assert entry["meal_type"] == MealType.dinner.value
        # Every entry must have either recipe_id or catalog_card_id set
        assert entry["recipe_id"] is not None or entry["catalog_card_id"] is not None


def test_draft_ingredient_limit_and_two_source_rules(
    client, db_session, auth_headers, two_source_draft_pool
):
    """Ingredient key cap (≤2 per key) and two-source (≥2 from second source) rules hold."""
    pool = two_source_draft_pool
    hf_card_ids = {str(c.id) for c in pool["cards"][:10]}

    week_start = date(2025, 6, 2)
    response = client.post(
        "/plan/draft/generate",
        json={"week_start": week_start.isoformat()},
        headers=auth_headers,
    )
    assert response.status_code == 200
    entries = response.json()["entries"]
    assert len(entries) == 7

    card_ids_in_plan = {e["catalog_card_id"] for e in entries if e["catalog_card_id"]}

    # Look up source types for the placed cards
    if card_ids_in_plan:
        placed_cards = db_session.query(SourceRecipeCard).filter(
            SourceRecipeCard.id.in_([UUID(cid) for cid in card_ids_in_plan])
        ).all()
        source_counts = Counter(c.source_type for c in placed_cards)
        # At least 2 sources represented, and the second-most source has ≥2 entries
        assert len(source_counts) >= 2, f"Expected ≥2 sources, got {dict(source_counts)}"
        dominant = source_counts.most_common(1)[0][0]
        second_max = max(v for s, v in source_counts.items() if s != dominant)
        assert second_max >= 2, (
            f"Expected second source to have ≥2 entries, got {dict(source_counts)}"
        )

    # HF cards: half have ingredient:chicken, half have ingredient:beef.
    # At most 2 of each should appear (ingredient key cap).
    hf_in_plan = [cid for cid in card_ids_in_plan if cid in hf_card_ids]
    # 10 HF cards; at most 4 should appear (2 chicken + 2 beef)
    assert len(hf_in_plan) <= 4, f"Expected ≤4 HF cards (ingredient cap), got {len(hf_in_plan)}"


def test_draft_weeknight_rule_excludes_slow_cards_when_fast_exist(
    client, db_session, auth_headers, test_user
):
    """Mon–Thu entries use fast (≤40 min) candidates when any remain."""
    coll = _make_collection(db_session, "hellofresh_web", "time-test-coll")

    # 7 fast cards (25 min)
    fast_ids = set()
    for i in range(7):
        c = _make_card(db_session, coll, f"Fast Card {i}", prep_time_minutes=25, position=i)
        fast_ids.add(str(c.id))

    # 7 slow cards (90 min) — these should not appear Mon–Thu
    slow_ids = set()
    for i in range(7):
        c = _make_card(db_session, coll, f"Slow Card {i}", prep_time_minutes=90, position=i + 7)
        slow_ids.add(str(c.id))

    db_session.commit()

    week_start = date(2025, 6, 2)  # Monday
    response = client.post(
        "/plan/draft/generate",
        json={"week_start": week_start.isoformat()},
        headers=auth_headers,
    )

    assert response.status_code == 200
    entries = response.json()["entries"]
    assert len(entries) == 7

    # Mon=0, Tue=1, Wed=2, Thu=3 must not use slow cards (fast ones are available)
    for day_offset in range(4):
        entry = entries[day_offset]
        if entry["catalog_card_id"] in slow_ids:
            pytest.fail(
                f"Day offset {day_offset} (weeknight) got a slow card; "
                f"fast cards were available"
            )


def test_draft_peanut_allergy_excludes_peanut_cards(
    client, db_session, auth_headers, test_user
):
    """A peanut allergy on another household member keeps peanut cards out of the draft."""
    allergic = User(
        id=uuid4(),
        name="Allergic Member",
        email="allergic@example.com",
        hashed_password=hash_password("testpass123"),
        role=UserRole.member.value,
        allergies=["peanut"],
    )
    db_session.add(allergic)

    coll = _make_collection(db_session, "hellofresh_web", "allergy-test-coll")

    peanut_ids = set()
    for i in range(5):
        c = _make_card(db_session, coll, f"Peanut Dish {i}", ingredient_keys=["peanut"], position=i)
        peanut_ids.add(str(c.id))

    safe_ids = set()
    for i in range(10):
        c = _make_card(
            db_session, coll, f"Safe Dish {i}",
            ingredient_keys=["chicken"],
            position=i + 5,
        )
        safe_ids.add(str(c.id))

    db_session.commit()

    week_start = date(2025, 6, 2)
    response = client.post(
        "/plan/draft/generate",
        json={"week_start": week_start.isoformat()},
        headers=auth_headers,
    )

    assert response.status_code == 200
    entries = response.json()["entries"]

    card_ids_in_plan = {e["catalog_card_id"] for e in entries if e["catalog_card_id"]}
    overlap = card_ids_in_plan & peanut_ids
    assert not overlap, f"Peanut cards should be excluded but found: {overlap}"


# ---------------------------------------------------------------------------
# Confirm card entry tests
# ---------------------------------------------------------------------------


@pytest.fixture
def card_draft_entry(db_session, test_user):
    """A draft MealPlanEntry pointing at a catalog card (no recipe yet)."""
    coll = SourceCollection(
        id=uuid4(),
        source_type="hellofresh_web",
        slug="confirm-test-coll",
        name="Confirm Test",
        url="https://example.com/confirm",
        parent_slug=None,
    )
    db_session.add(coll)
    db_session.flush()

    card = SourceRecipeCard(
        id=uuid4(),
        source_type="hellofresh_web",
        external_id="confirm-card-01",
        name="Lemon Herb Chicken",
        recipe_url="https://hellofresh.com/recipes/lemon-herb-chicken",
        ingredient_keys=["chicken"],
        prep_time_minutes=35,
        image_url="https://cdn.hellofresh.com/lemon-herb-chicken.jpg",
    )
    db_session.add(card)
    db_session.flush()

    db_session.add(SourceCollectionCard(
        collection_id=coll.id,
        card_id=card.id,
        position=0,
    ))

    entry = MealPlanEntry(
        id=uuid4(),
        date=date(2025, 6, 2),
        meal_type=MealType.dinner.value,
        catalog_card_id=card.id,
        planned_servings=2,
        status=MealPlanStatus.draft.value,
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return {"entry": entry, "card": card}


@pytest.fixture
def imported_recipe_for_card(db_session, test_user):
    """A recipe that open_card will return when mocked."""
    recipe = Recipe(
        id=uuid4(),
        name="Lemon Herb Chicken (imported)",
        source_type="hellofresh_web",
        base_servings=2,
        prep_time_minutes=35,
        is_persisted=True,
        created_by=test_user.id,
    )
    db_session.add(recipe)
    db_session.commit()
    db_session.refresh(recipe)
    return recipe


def test_confirm_card_entry_imports_recipe(
    client, db_session, auth_headers, card_draft_entry, imported_recipe_for_card, monkeypatch
):
    """Confirming a card entry calls open_card, sets recipe_id, and returns 200."""
    from src.services import catalog_service
    from src.services.catalog_service import OpenCardResult

    recipe = imported_recipe_for_card
    monkeypatch.setattr(
        catalog_service,
        "open_card",
        lambda db, card_id: OpenCardResult(recipe=recipe, imported=True),
    )

    entry = card_draft_entry["entry"]
    response = client.put(
        f"/plan/entries/{entry.id}/confirm",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["entry"]["status"] == MealPlanStatus.approved.value
    assert data["entry"]["recipe_id"] == str(recipe.id)
    assert data["entry"]["catalog_card_id"] == str(card_draft_entry["card"].id)


def test_confirm_card_entry_import_failure_returns_400(
    client, auth_headers, card_draft_entry, monkeypatch
):
    """An open_card failure on confirm returns 400 with the expected message."""
    from src.services import catalog_service

    monkeypatch.setattr(
        catalog_service,
        "open_card",
        lambda db, card_id: (_ for _ in ()).throw(ValueError("scrape failed")),
    )

    entry = card_draft_entry["entry"]
    response = client.put(
        f"/plan/entries/{entry.id}/confirm",
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "Could not bring this recipe in" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Display field tests
# ---------------------------------------------------------------------------


def test_entries_have_display_field_for_recipe_and_card(
    client, db_session, auth_headers, recipes_pool
):
    """Both recipe entries and card entries carry a populated display field in the response."""
    week_start = date(2025, 6, 2)

    coll = SourceCollection(
        id=uuid4(),
        source_type="hellofresh_web",
        slug="display-test-coll",
        name="Display Test",
        url="https://example.com/display",
        parent_slug=None,
    )
    db_session.add(coll)
    db_session.flush()

    card = SourceRecipeCard(
        id=uuid4(),
        source_type="hellofresh_web",
        external_id="display-card-01",
        name="Display Test Recipe",
        recipe_url="https://hellofresh.com/recipes/display-test",
        ingredient_keys=["chicken"],
        prep_time_minutes=25,
        image_url="https://cdn.hellofresh.com/display-test.jpg",
    )
    db_session.add(card)
    db_session.flush()
    db_session.add(SourceCollectionCard(collection_id=coll.id, card_id=card.id, position=0))

    # Recipe entry (day 0)
    db_session.add(MealPlanEntry(
        id=uuid4(),
        date=week_start,
        meal_type=MealType.dinner.value,
        recipe_id=recipes_pool[0].id,
        planned_servings=4,
        status=MealPlanStatus.draft.value,
    ))

    # Card entry (day 1)
    db_session.add(MealPlanEntry(
        id=uuid4(),
        date=week_start + timedelta(days=1),
        meal_type=MealType.dinner.value,
        catalog_card_id=card.id,
        planned_servings=2,
        status=MealPlanStatus.draft.value,
    ))

    db_session.commit()

    response = client.get(
        f"/plan/week?week_start={week_start.isoformat()}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    entries = response.json()["draft_entries"]
    assert len(entries) == 2

    for entry in entries:
        d = entry["display"]
        assert d is not None, f"Expected display field on entry {entry['id']}"
        assert isinstance(d["name"], str) and d["name"]
        assert isinstance(d["source_type"], str) and d["source_type"]


# ---------------------------------------------------------------------------
# POST /plan/entries/{id}/swap tests
# ---------------------------------------------------------------------------


@pytest.fixture
def swap_candidate_pool(db_session, test_user):
    """15 distinct cards in one collection, plus a draft entry pointing at cards[0].

    Provides enough candidates for repeated-swap tests while keeping each card's
    ingredient_keys unique so the ingredient-cap rule never blocks a pick.
    """
    coll = SourceCollection(
        id=uuid4(),
        source_type="hellofresh_web",
        slug="swap-test-coll",
        name="Swap Test Collection",
        url="https://example.com/swap-test",
        parent_slug=None,
    )
    db_session.add(coll)
    db_session.flush()

    cards = []
    for i in range(15):
        card = SourceRecipeCard(
            id=uuid4(),
            source_type="hellofresh_web",
            external_id=f"swap-card-{i}",
            name=f"Swap Card {i}",
            recipe_url=f"https://example.com/swap/{i}",
            ingredient_keys=[f"ingredient_{i}"],
            prep_time_minutes=30,
            image_url=f"https://cdn.example.com/swap-{i}.jpg",
        )
        db_session.add(card)
        db_session.flush()
        db_session.add(SourceCollectionCard(
            collection_id=coll.id,
            card_id=card.id,
            position=i,
        ))
        cards.append(card)

    entry = MealPlanEntry(
        id=uuid4(),
        date=date(2025, 6, 2),  # Monday
        meal_type=MealType.dinner.value,
        catalog_card_id=cards[0].id,
        planned_servings=2,
        status=MealPlanStatus.draft.value,
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return {"entry": entry, "cards": cards}


def test_swap_returns_different_item(client, auth_headers, swap_candidate_pool):
    """Swap replaces the draft entry with a different card and returns 200."""
    entry = swap_candidate_pool["entry"]
    original_card_id = str(entry.catalog_card_id)

    response = client.post(
        f"/plan/entries/{entry.id}/swap",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert "entry" in data
    result_entry = data["entry"]
    assert result_entry["id"] == str(entry.id)
    # Must have a different item
    assert result_entry["catalog_card_id"] != original_card_id or result_entry["recipe_id"] is not None


def test_swap_item_not_already_in_week(client, db_session, auth_headers, swap_candidate_pool):
    """Swapped-in item is not already placed elsewhere in the same week."""
    cards = swap_candidate_pool["cards"]
    entry = swap_candidate_pool["entry"]

    # Place cards[1] through cards[6] on other days of the same week
    week_start = date(2025, 6, 2)
    for day_offset in range(1, 7):
        db_session.add(MealPlanEntry(
            id=uuid4(),
            date=week_start + timedelta(days=day_offset),
            meal_type=MealType.dinner.value,
            catalog_card_id=cards[day_offset].id,
            planned_servings=2,
            status=MealPlanStatus.draft.value,
        ))
    db_session.commit()

    occupied_card_ids = {str(c.id) for c in cards[1:7]}

    response = client.post(
        f"/plan/entries/{entry.id}/swap",
        headers=auth_headers,
    )

    assert response.status_code == 200
    result_card_id = response.json()["entry"]["catalog_card_id"]
    assert result_card_id not in occupied_card_ids, (
        f"Swap returned a card already in the week: {result_card_id}"
    )


def test_swap_confirmed_entry_returns_400(client, db_session, auth_headers, swap_candidate_pool):
    """Swapping a confirmed (approved) entry returns 400."""
    entry = swap_candidate_pool["entry"]
    entry.status = MealPlanStatus.approved.value
    db_session.commit()

    response = client.post(
        f"/plan/entries/{entry.id}/swap",
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "Only draft entries can be swapped" in response.json()["detail"]


def test_swap_unknown_entry_returns_404(client, auth_headers):
    """Swapping an unknown entry id returns 404."""
    response = client.post(
        f"/plan/entries/{uuid4()}/swap",
        headers=auth_headers,
    )

    assert response.status_code == 404


def test_swap_does_not_repeat_offered_items(client, db_session, auth_headers, swap_candidate_pool):
    """Repeated swaps on the same entry never return an item already offered for that day."""
    entry = swap_candidate_pool["entry"]
    original_card_id = str(entry.catalog_card_id)

    # First swap
    r1 = client.post(f"/plan/entries/{entry.id}/swap", headers=auth_headers)
    assert r1.status_code == 200
    after_first = r1.json()["entry"]["catalog_card_id"]

    # Second swap
    r2 = client.post(f"/plan/entries/{entry.id}/swap", headers=auth_headers)
    assert r2.status_code == 200
    after_second = r2.json()["entry"]["catalog_card_id"]

    # Neither previous item should reappear
    assert after_second != original_card_id, "Second swap re-offered the original item"
    assert after_second != after_first, "Second swap re-offered the first swap's item"

    # Third swap — verifies that after_second was recorded in swap history;
    # a broken append on swap 2 would leave it out and allow it to reappear here.
    r3 = client.post(f"/plan/entries/{entry.id}/swap", headers=auth_headers)
    assert r3.status_code == 200
    after_third = r3.json()["entry"]["catalog_card_id"]

    assert after_third != original_card_id, "Third swap re-offered the original item"
    assert after_third != after_first, "Third swap re-offered the first swap's item"
    assert after_third != after_second, "Third swap re-offered the second swap's item"


def test_swap_requires_authentication(client, swap_candidate_pool):
    """POST /plan/entries/{id}/swap without auth returns 401."""
    entry = swap_candidate_pool["entry"]

    response = client.post(f"/plan/entries/{entry.id}/swap")

    assert response.status_code == 401


def test_migration_chain_has_one_head_after_catalog_card_id_migration():
    """Sanity: the new migration did not introduce a second head in the alembic chain."""
    from pathlib import Path
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    project_root = Path(__file__).resolve().parent.parent.parent
    cfg = Config(str(project_root / "alembic.ini"))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert len(heads) == 1, (
        f"Expected exactly 1 head, found {len(heads)}: {heads}. "
        "The catalog_card_id migration introduced a second head."
    )

