"""
Recipe themes router.

GET /themes returns each theme (cuisine, main ingredient, dish type, diet,
meal type, source) with its values and the lists behind them, so the Recipes
page can build theme pages and filter whole lists by a value.
"""

import logging
from dataclasses import asdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.db.models.user import User
from src.middleware.auth import get_current_user
from src.schemas.theme import Theme
from src.services.recipe_themes import build_themes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/themes", tags=["themes"])


@router.get("", response_model=list[Theme])
def list_themes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Theme]:
    """
    List recipe themes with their values.

    Database-only: never contacts a source. Collections appear once the
    catalog has been seeded (GET /catalog/{source}/collections does that).
    """
    return [Theme.model_validate(asdict(theme)) for theme in build_themes(db)]
