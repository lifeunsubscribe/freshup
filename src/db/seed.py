"""Seed data for FreshUp. Idempotent — safe to re-run.

Usage: python -m src.db.seed
"""

from uuid import uuid4

from sqlalchemy import select

from src.config import get_settings
from src.db.database import init_engine, get_session_factory
from src.db.models import Store, User
from src.db.models.user import UserRole


STORES = [
    {"name": "Costco", "has_digital_receipts": True},
    {"name": "Save-A-Lot", "has_digital_receipts": False},
    {"name": "King Soopers", "has_digital_receipts": False},
    {"name": "Walmart", "has_digital_receipts": False},
]

TEST_USER = {
    "name": "Sarah",
    "role": UserRole.coordinator.value,
    "dietary_profile": ["omnivore"],
}


def seed() -> None:
    settings = get_settings()
    init_engine(settings.database_url)
    session_factory = get_session_factory()

    with session_factory() as session:
        # Seed stores
        for store_data in STORES:
            exists = session.execute(
                select(Store).where(Store.name == store_data["name"])
            ).scalar_one_or_none()
            if not exists:
                session.add(Store(id=uuid4(), **store_data))
                print(f"  Added store: {store_data['name']}")
            else:
                print(f"  Store already exists: {store_data['name']}")

        # Seed test user
        exists = session.execute(
            select(User).where(User.name == TEST_USER["name"])
        ).scalar_one_or_none()
        if not exists:
            session.add(User(id=uuid4(), **TEST_USER))
            print(f"  Added user: {TEST_USER['name']}")
        else:
            print(f"  User already exists: {TEST_USER['name']}")

        session.commit()
        print("Seed complete.")


if __name__ == "__main__":
    seed()
