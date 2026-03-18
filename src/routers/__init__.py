# API route handlers will be organized here by domain:
# - auth.py (1C - authentication endpoints)
# - users.py (1C - user management endpoints)
# - inventory.py (1D)
# - recipes.py (1E)
# - grocery.py (1F)
# - prepared_foods.py (1G)

from src.routers.auth import router as auth_router
from src.routers.users import router as users_router

__all__ = ["auth_router", "users_router"]
