# API route handlers will be organized here by domain:
# - auth.py (1C - authentication endpoints)
# - users.py (1C - user management endpoints)
# - inventory.py (1D)
# - recipes.py (1E)
# - grocery.py (1F)
# - prepared_foods.py (1G)
# - scraper.py (2C - scraper/import endpoints)
# - feed.py (2.5C - personalized recipe feed)
# - plan.py (2.5E - meal plan endpoints)

from src.routers.auth import router as auth_router
from src.routers.users import router as users_router
from src.routers.substitutions import router as substitutions_router
from src.routers.inventory import router as inventory_router
from src.routers.recipes import router as recipes_router
from src.routers.grocery import router as grocery_router
from src.routers.prepared_foods import router as prepared_foods_router
from src.routers.scraper import router as scraper_router
from src.routers.tasks import router as tasks_router
from src.routers.receipts import router as receipts_router
from src.routers.feed import router as feed_router
from src.routers.menus import router as menus_router
from src.routers.plan import router as plan_router

__all__ = ["auth_router", "users_router", "substitutions_router", "inventory_router", "recipes_router", "grocery_router", "prepared_foods_router", "scraper_router", "tasks_router", "receipts_router", "feed_router", "menus_router", "plan_router"]
