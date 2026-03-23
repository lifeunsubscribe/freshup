"""Seed data for FreshUp. Idempotent — safe to re-run.

Usage: python -m src.db.seed
"""

from uuid import uuid4

from sqlalchemy import select

from src.config import get_settings
from src.db.database import init_engine, get_session_factory
from src.db.models import Store, User
from src.db.models.user import UserRole
from src.services.auth_service import hash_password


STORES = [
    {"name": "Costco", "has_digital_receipts": True},
    {"name": "Save-A-Lot", "has_digital_receipts": False},
    {"name": "King Soopers", "has_digital_receipts": False},
    {"name": "Walmart", "has_digital_receipts": False},
]

SEED_USERS = [
    {
        "name": "Sarah",
        "email": "sarah@freshup.local",
        "password": "FreshUp2024!",
        "role": UserRole.coordinator.value,
        "dietary_profile": ["omnivore"],
    },
    {
        "name": "Alex",
        "email": "alex@freshup.local",
        "password": "FreshUp2024!",
        "role": UserRole.member.value,
        "dietary_profile": ["vegan"],
    },
]


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

        # Seed users
        for user_data in SEED_USERS:
            exists = session.execute(
                select(User).where(User.email == user_data["email"])
            ).scalar_one_or_none()
            if not exists:
                session.add(User(
                    id=uuid4(),
                    name=user_data["name"],
                    email=user_data["email"],
                    hashed_password=hash_password(user_data["password"]),
                    role=user_data["role"],
                    dietary_profile=user_data["dietary_profile"],
                ))
                print(f"  Added user: {user_data['name']} (email: {user_data['email']}, password: {user_data['password']})")
            else:
                print(f"  User already exists: {user_data['name']}")

        session.commit()
        print("Seed complete.")


if __name__ == "__main__":
    seed()
