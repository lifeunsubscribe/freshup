"""All SQLAlchemy models — single import point for Alembic and app code."""

from src.db.models.user import User, UserRole, DietaryProfile
from src.db.models.auth_audit_log import AuthAuditLog, AuthEventType
from src.db.models.store import Store
from src.db.models.inventory_item import (
    InventoryItem,
    Category,
    UnitType,
    StorageLocation,
    Shareability,
    inventory_store_association,
)
from src.db.models.recipe import Recipe, SourceType
from src.db.models.recipe_ingredient import RecipeIngredient
from src.db.models.prepared_food import PreparedFood, PreparedFoodType
from src.db.models.meal_plan import (
    MealPlanEntry,
    WeeklyMealPlanVote,
    MealType,
    MealPlanStatus,
    VotingStatus,
    meal_plan_user_association,
)
from src.db.models.grocery_list import GroceryListItem, GrocerySource
from src.db.models.substitution import SubstitutionPreference, SubstitutionContext
from src.db.models.consumption_pattern import ConsumptionPattern
from src.db.models.user_recipe import UserRecipeRating
from src.db.models.processing_task import ProcessingTask, TaskType, TaskStatus

__all__ = [
    "User",
    "UserRole",
    "DietaryProfile",
    "AuthAuditLog",
    "AuthEventType",
    "Store",
    "InventoryItem",
    "Category",
    "UnitType",
    "StorageLocation",
    "Shareability",
    "inventory_store_association",
    "Recipe",
    "SourceType",
    "RecipeIngredient",
    "PreparedFood",
    "PreparedFoodType",
    "MealPlanEntry",
    "WeeklyMealPlanVote",
    "MealType",
    "MealPlanStatus",
    "VotingStatus",
    "meal_plan_user_association",
    "GroceryListItem",
    "GrocerySource",
    "SubstitutionPreference",
    "SubstitutionContext",
    "ConsumptionPattern",
    "UserRecipeRating",
    "ProcessingTask",
    "TaskType",
    "TaskStatus",
]
