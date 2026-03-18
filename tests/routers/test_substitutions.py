"""
Integration tests for substitution preference endpoints.

Tests cover:
- POST /users/me/substitutions: create preferences with validation
- GET /users/me/substitutions: list all user preferences
- GET /users/me/substitutions/{id}: get single preference
- PUT /users/me/substitutions/{id}: update replacements and context
- DELETE /users/me/substitutions/{id}: delete preference
- Cross-user access prevention
- Authentication requirements
- Validation (replacements format, context enum, unique ranks)
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from uuid import uuid4

from src.db.database import Base, get_db
from src.db import models
from src.db.models.user import User, UserRole
from src.db.models.substitution import SubstitutionPreference
from src.services.auth_service import hash_password, create_access_token

from fastapi import FastAPI
from src.routers import substitutions_router

# Create a test app without lifespan
app = FastAPI(
    title="FreshUp",
    description="Privacy-first kitchen management system",
    version="0.1.0",
)

# Register the substitutions router
app.include_router(substitutions_router)


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
    """Create a test user in the database."""
    user = User(
        id=uuid4(),
        name="Test User",
        email="test@example.com",
        hashed_password=hash_password("TestPass123!"),
        role=UserRole.member.value,
        dietary_profile=["vegetarian"],
        allergies=["peanuts"],
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def second_user(db_session):
    """Create a second test user for cross-user access tests."""
    user = User(
        id=uuid4(),
        name="Second User",
        email="second@example.com",
        hashed_password=hash_password("TestPass123!"),
        role=UserRole.member.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    """Create authentication headers with a valid JWT token."""
    token = create_access_token(data={"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def second_auth_headers(second_user):
    """Create authentication headers for the second user."""
    token = create_access_token(data={"sub": str(second_user.id)})
    return {"Authorization": f"Bearer {token}"}


class TestCreateSubstitutionPreference:
    """Tests for POST /users/me/substitutions endpoint."""

    def test_create_preference_success(self, client, auth_headers):
        """Successfully create a substitution preference."""
        payload = {
            "original_ingredient": "broccoli",
            "replacements": [
                {"ingredient": "asparagus", "rank": 1},
                {"ingredient": "green beans", "rank": 2}
            ],
            "context": "side_dish"
        }

        response = client.post("/users/me/substitutions", json=payload, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["original_ingredient"] == "broccoli"
        assert len(data["replacements"]) == 2
        assert data["context"] == "side_dish"
        assert "id" in data
        assert "user_id" in data

    def test_create_preference_default_context(self, client, auth_headers):
        """Create preference without context defaults to 'any'."""
        payload = {
            "original_ingredient": "milk",
            "replacements": [
                {"ingredient": "almond milk", "rank": 1}
            ]
        }

        response = client.post("/users/me/substitutions", json=payload, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["context"] == "any"

    def test_create_preference_unauthorized(self, client):
        """Endpoint requires authentication."""
        payload = {
            "original_ingredient": "broccoli",
            "replacements": [{"ingredient": "asparagus", "rank": 1}],
        }

        response = client.post("/users/me/substitutions", json=payload)

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    @pytest.mark.parametrize("context_value", [
        "side_dish",
        "in_recipe",
        "protein",
        "sauce",
        "any"
    ])
    def test_create_preference_all_valid_contexts(self, client, auth_headers, context_value):
        """All SubstitutionContext enum values are accepted."""
        payload = {
            "original_ingredient": "broccoli",
            "replacements": [{"ingredient": "asparagus", "rank": 1}],
            "context": context_value
        }

        response = client.post("/users/me/substitutions", json=payload, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["context"] == context_value

    def test_create_preference_invalid_context(self, client, auth_headers):
        """Invalid context enum value returns 422."""
        payload = {
            "original_ingredient": "broccoli",
            "replacements": [{"ingredient": "asparagus", "rank": 1}],
            "context": "invalid_context"
        }

        response = client.post("/users/me/substitutions", json=payload, headers=auth_headers)

        assert response.status_code == 422

    def test_create_preference_empty_ingredient(self, client, auth_headers):
        """Empty original ingredient returns 422."""
        payload = {
            "original_ingredient": "   ",
            "replacements": [{"ingredient": "asparagus", "rank": 1}],
        }

        response = client.post("/users/me/substitutions", json=payload, headers=auth_headers)

        assert response.status_code == 422

    def test_create_preference_empty_replacements(self, client, auth_headers):
        """Empty replacements list returns 422."""
        payload = {
            "original_ingredient": "broccoli",
            "replacements": [],
        }

        response = client.post("/users/me/substitutions", json=payload, headers=auth_headers)

        assert response.status_code == 422

    def test_create_preference_duplicate_ranks(self, client, auth_headers):
        """Duplicate ranks in replacements returns 422."""
        payload = {
            "original_ingredient": "broccoli",
            "replacements": [
                {"ingredient": "asparagus", "rank": 1},
                {"ingredient": "green beans", "rank": 1}
            ],
        }

        response = client.post("/users/me/substitutions", json=payload, headers=auth_headers)

        assert response.status_code == 422

    def test_create_preference_invalid_rank(self, client, auth_headers):
        """Rank less than 1 returns 422."""
        payload = {
            "original_ingredient": "broccoli",
            "replacements": [
                {"ingredient": "asparagus", "rank": 0}
            ],
        }

        response = client.post("/users/me/substitutions", json=payload, headers=auth_headers)

        assert response.status_code == 422

    def test_create_preference_accepts_unicode_ingredients(self, client, auth_headers):
        """Successfully create preference with Unicode ingredient names including CJK."""
        payload = {
            "original_ingredient": "jalapeño",
            "replacements": [
                {"ingredient": "crème fraîche", "rank": 1},
                {"ingredient": "café beans", "rank": 2},
                {"ingredient": "豆腐", "rank": 3}  # tofu in Japanese (CJK)
            ],
            "context": "any"
        }

        response = client.post("/users/me/substitutions", json=payload, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["original_ingredient"] == "jalapeño"
        assert any(r["ingredient"] == "crème fraîche" for r in data["replacements"])
        assert any(r["ingredient"] == "café beans" for r in data["replacements"])
        assert any(r["ingredient"] == "豆腐" for r in data["replacements"])

    def test_create_preference_rejects_control_characters_in_replacement(self, client, auth_headers):
        """Reject ingredients with control characters in replacement."""
        payload = {
            "original_ingredient": "broccoli",
            "replacements": [
                {"ingredient": "asparagus\x00with\x00nulls", "rank": 1}
            ],
        }

        response = client.post("/users/me/substitutions", json=payload, headers=auth_headers)

        assert response.status_code == 422

    def test_create_preference_rejects_control_characters_in_original(self, client, auth_headers):
        """Reject ingredients with control characters in original_ingredient."""
        payload = {
            "original_ingredient": "broccoli\x00with\x00nulls",
            "replacements": [
                {"ingredient": "asparagus", "rank": 1}
            ],
        }

        response = client.post("/users/me/substitutions", json=payload, headers=auth_headers)

        assert response.status_code == 422

    def test_create_preference_rejects_zero_width_characters(self, client, auth_headers):
        """Reject ingredients with zero-width characters."""
        payload = {
            "original_ingredient": "broccoli",
            "replacements": [
                {"ingredient": "asparagus\u200bwith\u200bzwsp", "rank": 1}
            ],
        }

        response = client.post("/users/me/substitutions", json=payload, headers=auth_headers)

        assert response.status_code == 422

    def test_create_preference_rejects_whitespace_with_zero_width_characters(self, client, auth_headers):
        """Reject ingredients that are effectively empty after stripping (whitespace + zero-width chars)."""
        payload = {
            "original_ingredient": "broccoli",
            "replacements": [
                {"ingredient": "   \u200b\u200c\u200d\ufeff   ", "rank": 1}  # spaces + ZWSP + ZWNJ + ZWJ + ZWNBSP + spaces
            ],
        }

        response = client.post("/users/me/substitutions", json=payload, headers=auth_headers)

        assert response.status_code == 422

    def test_create_preference_rejects_whitespace_with_zero_width_characters_in_original(self, client, auth_headers):
        """Reject original_ingredient that is effectively empty after stripping (whitespace + zero-width chars)."""
        payload = {
            "original_ingredient": "   \u200b\u200c\u200d\ufeff   ",  # spaces + ZWSP + ZWNJ + ZWJ + ZWNBSP + spaces
            "replacements": [
                {"ingredient": "asparagus", "rank": 1}
            ],
        }

        response = client.post("/users/me/substitutions", json=payload, headers=auth_headers)

        assert response.status_code == 422

    def test_create_preference_normalizes_unicode(self, client, auth_headers):
        """Unicode is normalized to NFC form."""
        payload = {
            "original_ingredient": "cafe\u0301",  # café with combining accent (e + acute)
            "replacements": [
                {"ingredient": "cre\u0300me", "rank": 1}  # crème with combining accent (e + grave + m + e)
            ],
        }

        response = client.post("/users/me/substitutions", json=payload, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        # Should be normalized to NFC
        assert data["original_ingredient"] == "café"
        assert data["replacements"][0]["ingredient"] == "crème"


class TestListSubstitutionPreferences:
    """Tests for GET /users/me/substitutions endpoint."""

    def test_list_preferences_empty(self, client, auth_headers):
        """List returns empty array when user has no preferences."""
        response = client.get("/users/me/substitutions", headers=auth_headers)

        assert response.status_code == 200
        assert response.json() == []

    def test_list_preferences_multiple(self, client, db_session, test_user, auth_headers):
        """List returns all user's preferences ordered by original_ingredient."""
        # Create multiple preferences
        pref1 = SubstitutionPreference(
            user_id=test_user.id,
            original_ingredient="zucchini",
            replacements=[{"ingredient": "squash", "rank": 1}],
            context="side_dish"
        )
        pref2 = SubstitutionPreference(
            user_id=test_user.id,
            original_ingredient="broccoli",
            replacements=[{"ingredient": "asparagus", "rank": 1}],
            context="any"
        )
        db_session.add_all([pref1, pref2])
        db_session.commit()

        response = client.get("/users/me/substitutions", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        # Should be ordered alphabetically by original_ingredient
        assert data[0]["original_ingredient"] == "broccoli"
        assert data[1]["original_ingredient"] == "zucchini"

    def test_list_preferences_only_own(self, client, db_session, test_user, second_user, auth_headers):
        """List only returns current user's preferences, not other users'."""
        # Create preferences for both users
        pref1 = SubstitutionPreference(
            user_id=test_user.id,
            original_ingredient="broccoli",
            replacements=[{"ingredient": "asparagus", "rank": 1}],
        )
        pref2 = SubstitutionPreference(
            user_id=second_user.id,
            original_ingredient="milk",
            replacements=[{"ingredient": "almond milk", "rank": 1}],
        )
        db_session.add_all([pref1, pref2])
        db_session.commit()

        response = client.get("/users/me/substitutions", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["original_ingredient"] == "broccoli"

    def test_list_preferences_unauthorized(self, client):
        """Endpoint requires authentication."""
        response = client.get("/users/me/substitutions")

        assert response.status_code == 401


class TestGetSubstitutionPreference:
    """Tests for GET /users/me/substitutions/{id} endpoint."""

    def test_get_preference_success(self, client, db_session, test_user, auth_headers):
        """Successfully retrieve a single preference."""
        pref = SubstitutionPreference(
            user_id=test_user.id,
            original_ingredient="broccoli",
            replacements=[{"ingredient": "asparagus", "rank": 1}],
            context="side_dish"
        )
        db_session.add(pref)
        db_session.commit()
        db_session.refresh(pref)

        response = client.get(f"/users/me/substitutions/{pref.id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(pref.id)
        assert data["original_ingredient"] == "broccoli"

    def test_get_preference_not_found(self, client, auth_headers):
        """Non-existent ID returns 404."""
        fake_id = uuid4()
        response = client.get(f"/users/me/substitutions/{fake_id}", headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Substitution preference not found"

    def test_get_preference_cross_user_access(self, client, db_session, second_user, auth_headers):
        """Cannot access another user's preference."""
        pref = SubstitutionPreference(
            user_id=second_user.id,
            original_ingredient="broccoli",
            replacements=[{"ingredient": "asparagus", "rank": 1}],
        )
        db_session.add(pref)
        db_session.commit()
        db_session.refresh(pref)

        response = client.get(f"/users/me/substitutions/{pref.id}", headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Substitution preference not found"

    def test_get_preference_unauthorized(self, client, db_session, test_user):
        """Endpoint requires authentication."""
        pref = SubstitutionPreference(
            user_id=test_user.id,
            original_ingredient="broccoli",
            replacements=[{"ingredient": "asparagus", "rank": 1}],
        )
        db_session.add(pref)
        db_session.commit()
        db_session.refresh(pref)

        response = client.get(f"/users/me/substitutions/{pref.id}")

        assert response.status_code == 401


class TestUpdateSubstitutionPreference:
    """Tests for PUT /users/me/substitutions/{id} endpoint."""

    def test_update_replacements(self, client, db_session, test_user, auth_headers):
        """Successfully update replacements list."""
        pref = SubstitutionPreference(
            user_id=test_user.id,
            original_ingredient="broccoli",
            replacements=[{"ingredient": "asparagus", "rank": 1}],
            context="side_dish"
        )
        db_session.add(pref)
        db_session.commit()
        db_session.refresh(pref)

        update_payload = {
            "replacements": [
                {"ingredient": "asparagus", "rank": 1},
                {"ingredient": "carrots", "rank": 2},
                {"ingredient": "green beans", "rank": 3}
            ]
        }

        response = client.put(
            f"/users/me/substitutions/{pref.id}",
            json=update_payload,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["replacements"]) == 3
        assert data["context"] == "side_dish"  # Unchanged

    def test_update_context(self, client, db_session, test_user, auth_headers):
        """Successfully update context."""
        pref = SubstitutionPreference(
            user_id=test_user.id,
            original_ingredient="broccoli",
            replacements=[{"ingredient": "asparagus", "rank": 1}],
            context="side_dish"
        )
        db_session.add(pref)
        db_session.commit()
        db_session.refresh(pref)

        update_payload = {"context": "any"}

        response = client.put(
            f"/users/me/substitutions/{pref.id}",
            json=update_payload,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["context"] == "any"
        assert len(data["replacements"]) == 1  # Unchanged

    def test_update_both_fields(self, client, db_session, test_user, auth_headers):
        """Successfully update both replacements and context."""
        pref = SubstitutionPreference(
            user_id=test_user.id,
            original_ingredient="broccoli",
            replacements=[{"ingredient": "asparagus", "rank": 1}],
            context="side_dish"
        )
        db_session.add(pref)
        db_session.commit()
        db_session.refresh(pref)

        update_payload = {
            "replacements": [{"ingredient": "carrots", "rank": 1}],
            "context": "protein"
        }

        response = client.put(
            f"/users/me/substitutions/{pref.id}",
            json=update_payload,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["context"] == "protein"
        assert data["replacements"][0]["ingredient"] == "carrots"

    def test_update_preference_not_found(self, client, auth_headers):
        """Non-existent ID returns 404."""
        fake_id = uuid4()
        update_payload = {"context": "any"}

        response = client.put(
            f"/users/me/substitutions/{fake_id}",
            json=update_payload,
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_update_cross_user_access(self, client, db_session, second_user, auth_headers):
        """Cannot update another user's preference."""
        pref = SubstitutionPreference(
            user_id=second_user.id,
            original_ingredient="broccoli",
            replacements=[{"ingredient": "asparagus", "rank": 1}],
        )
        db_session.add(pref)
        db_session.commit()
        db_session.refresh(pref)

        update_payload = {"context": "any"}

        response = client.put(
            f"/users/me/substitutions/{pref.id}",
            json=update_payload,
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_update_invalid_context(self, client, db_session, test_user, auth_headers):
        """Invalid context enum value returns 422."""
        pref = SubstitutionPreference(
            user_id=test_user.id,
            original_ingredient="broccoli",
            replacements=[{"ingredient": "asparagus", "rank": 1}],
        )
        db_session.add(pref)
        db_session.commit()
        db_session.refresh(pref)

        update_payload = {"context": "invalid_context"}

        response = client.put(
            f"/users/me/substitutions/{pref.id}",
            json=update_payload,
            headers=auth_headers
        )

        assert response.status_code == 422

    def test_update_unauthorized(self, client, db_session, test_user):
        """Endpoint requires authentication."""
        pref = SubstitutionPreference(
            user_id=test_user.id,
            original_ingredient="broccoli",
            replacements=[{"ingredient": "asparagus", "rank": 1}],
        )
        db_session.add(pref)
        db_session.commit()
        db_session.refresh(pref)

        update_payload = {"context": "any"}

        response = client.put(f"/users/me/substitutions/{pref.id}", json=update_payload)

        assert response.status_code == 401


class TestDeleteSubstitutionPreference:
    """Tests for DELETE /users/me/substitutions/{id} endpoint."""

    def test_delete_preference_success(self, client, db_session, test_user, auth_headers):
        """Successfully delete a preference."""
        pref = SubstitutionPreference(
            user_id=test_user.id,
            original_ingredient="broccoli",
            replacements=[{"ingredient": "asparagus", "rank": 1}],
        )
        db_session.add(pref)
        db_session.commit()
        db_session.refresh(pref)
        pref_id = pref.id

        response = client.delete(f"/users/me/substitutions/{pref_id}", headers=auth_headers)

        assert response.status_code == 204

        # Verify deletion
        deleted_pref = db_session.query(SubstitutionPreference).filter(
            SubstitutionPreference.id == pref_id
        ).first()
        assert deleted_pref is None

    def test_delete_preference_not_found(self, client, auth_headers):
        """Non-existent ID returns 404."""
        fake_id = uuid4()
        response = client.delete(f"/users/me/substitutions/{fake_id}", headers=auth_headers)

        assert response.status_code == 404

    def test_delete_cross_user_access(self, client, db_session, second_user, auth_headers):
        """Cannot delete another user's preference."""
        pref = SubstitutionPreference(
            user_id=second_user.id,
            original_ingredient="broccoli",
            replacements=[{"ingredient": "asparagus", "rank": 1}],
        )
        db_session.add(pref)
        db_session.commit()
        db_session.refresh(pref)

        response = client.delete(f"/users/me/substitutions/{pref.id}", headers=auth_headers)

        assert response.status_code == 404

        # Verify preference still exists
        existing_pref = db_session.query(SubstitutionPreference).filter(
            SubstitutionPreference.id == pref.id
        ).first()
        assert existing_pref is not None

    def test_delete_unauthorized(self, client, db_session, test_user):
        """Endpoint requires authentication."""
        pref = SubstitutionPreference(
            user_id=test_user.id,
            original_ingredient="broccoli",
            replacements=[{"ingredient": "asparagus", "rank": 1}],
        )
        db_session.add(pref)
        db_session.commit()
        db_session.refresh(pref)

        response = client.delete(f"/users/me/substitutions/{pref.id}")

        assert response.status_code == 401
