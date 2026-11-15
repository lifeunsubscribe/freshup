"""add taste_preferences and onboarded_at to users

Revision ID: sl4ntia2uyc
Revises: rk3mshza1txb
Create Date: 2026-11-15 00:00:00.000000

"""
from typing import Sequence, Union
import json
import re

from alembic import op
import sqlalchemy as sa
from sqlalchemy import Table, MetaData


# revision identifiers, used by Alembic.
revision: str = 'sl4ntia2uyc'
down_revision: Union[str, None] = 'carding01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Frozen vocabulary snapshot — Phase 2.5J, 2026-11-15.
# Embedding the spellings here makes the data migration deterministic: a
# future change to src/services/ingredient_keys.py will NOT alter how existing
# rows were backfilled.  key → [spellings] (longest spellings must come first
# when multi-word spellings share a prefix with single-word ones).
# ---------------------------------------------------------------------------
_FROZEN_SPELLINGS: dict[str, list[str]] = {
    "chicken": ["chicken breast", "chicken thigh", "chicken wing", "chicken", "poultry"],
    "turkey": ["turkey"],
    "duck": ["duck"],
    "beef": ["ground beef", "beef", "steak", "sirloin", "ribeye", "flank steak", "brisket", "chuck"],
    "pork": ["pork loin", "pork chop", "pork belly", "pork", "ham", "prosciutto", "pancetta"],
    "lamb": ["lamb chop", "lamb", "mutton"],
    "veal": ["veal"],
    "salmon": ["salmon"],
    "shrimp": ["shrimp", "prawn"],
    "white-fish": ["tilapia", "cod", "haddock", "catfish", "barramundi", "halibut", "flounder"],
    "tuna": ["tuna"],
    "crab": ["crab"],
    "lobster": ["lobster"],
    "clam": ["clam"],
    "oyster": ["oyster"],
    "scallop": ["scallop"],
    "anchovy": ["anchovy"],
    "sardine": ["sardine"],
    "seafood": ["seafood"],
    "tofu": ["tofu", "tempeh"],
    "sausage": ["sausage", "chorizo", "bratwurst", "kielbasa"],
    "bacon": ["bacon"],
    "beans-legumes": [
        "black bean", "kidney bean", "pinto bean", "cannellini bean", "navy bean",
        "chickpea", "lentil", "pea", "split pea", "bean", "legume",
    ],
    "edamame": ["edamame", "soybean", "soy bean"],
    "grains": ["quinoa", "farro", "barley", "millet", "bulgur", "oat", "grain"],
    "rice": ["brown rice", "jasmine rice", "basmati rice", "arborio rice", "fried rice",
             "risotto rice", "rice"],
    "pasta": ["pasta", "spaghetti", "penne", "fettuccine", "linguine", "rigatoni",
              "fusilli", "orzo", "noodle"],
    "bread": ["sourdough", "baguette", "naan", "pita", "flatbread", "brioche", "bread"],
    "couscous": ["couscous"],
    "tortilla": ["flour tortilla", "tortilla"],
    "corn-tortilla": ["corn tortilla"],
    "rice-noodles": ["rice noodle", "rice vermicelli", "rice stick"],
    "wheat": ["flour", "wheat", "all-purpose flour", "whole wheat flour"],
    "sweet-potato": ["sweet potato"],
    "potatoes": ["potato", "mashed potato", "yukon gold", "russet potato"],
    "corn": ["corn", "maize"],
    "cornstarch": ["cornstarch", "corn starch"],
    "potato-starch": ["potato starch"],
    "broccoli": ["broccolini", "broccoli"],
    "cauliflower": ["cauliflower"],
    "spinach": ["spinach"],
    "kale": ["kale"],
    "cabbage": ["bok choy", "cabbage", "napa cabbage"],
    "lettuce": ["romaine", "arugula", "lettuce"],
    "tomato": ["cherry tomato", "grape tomato", "roma tomato", "tomato"],
    "pepper": ["bell pepper", "red bell pepper", "green bell pepper", "red pepper",
               "green pepper", "yellow pepper"],
    "chili-flakes": ["red pepper flake", "crushed red pepper", "chili flake", "chilli flake"],
    "onion": ["red onion", "yellow onion", "white onion", "green onion", "scallion",
              "shallot", "leek", "onion"],
    "garlic": ["garlic"],
    "carrot": ["carrot"],
    "celery": ["celery"],
    "zucchini": ["zucchini", "courgette"],
    "eggplant": ["eggplant", "aubergine"],
    "asparagus": ["asparagus"],
    "green-beans": ["green bean", "green beans", "haricot vert"],
    "mushrooms": ["portobello", "cremini", "shiitake", "oyster mushroom", "mushroom"],
    "cucumber": ["cucumber"],
    "artichoke": ["artichoke"],
    "lemon": ["lemon"],
    "lemon-juice": ["lemon juice"],
    "lemon-zest": ["lemon zest"],
    "lime": ["lime"],
    "lime-juice": ["lime juice"],
    "lime-zest": ["lime zest"],
    "avocado": ["avocado"],
    "apple": ["apple"],
    "mango": ["mango"],
    "milk": ["whole milk", "skim milk", "milk"],
    "coconut": ["shredded coconut", "coconut flake", "coconut"],
    "coconut-milk": ["coconut milk"],
    "coconut-cream": ["coconut cream"],
    "coconut-oil": ["coconut oil"],
    "almond-milk": ["almond milk"],
    "soy-milk": ["soy milk", "soymilk"],
    "oat-milk": ["oat milk"],
    "cashew-cream": ["cashew cream", "cashew milk"],
    "buttermilk": ["buttermilk"],
    "cream": ["heavy cream", "whipping cream", "cream"],
    "sour-cream": ["sour cream"],
    "cream-cheese": ["cream cheese"],
    "butter": ["butter"],
    "cheese": [
        "mozzarella", "cheddar", "parmesan", "feta", "brie", "gouda", "ricotta",
        "gruyere", "cotija", "monterey jack", "cheese",
    ],
    "yogurt": ["greek yogurt", "yogurt"],
    "egg": ["egg white", "egg yolk", "egg"],
    "peanut": ["peanut"],
    "peanut-butter": ["peanut butter"],
    "peanut-oil": ["peanut oil"],
    "almond": ["almond"],
    "almond-butter": ["almond butter"],
    "walnut": ["walnut"],
    "pecan": ["pecan"],
    "cashew": ["cashew"],
    "pine-nut": ["pine nut"],
    "pistachio": ["pistachio"],
    "sesame": ["sesame seed", "sesame"],
    "sesame-oil": ["toasted sesame oil", "sesame oil"],
    "tahini": ["tahini"],
    "sunflower-seed": ["sunflower seed"],
    "flaxseed": ["flaxseed", "flax seed"],
    "olive-oil": ["olive oil"],
    "soy-sauce": ["soy sauce", "tamari"],
    "coconut-aminos": ["coconut aminos"],
    "fish-sauce": ["fish sauce"],
    "oyster-sauce": ["oyster sauce"],
    "worcestershire": ["worcestershire sauce", "worcestershire"],
    "shrimp-paste": ["shrimp paste"],
    "anchovy-paste": ["anchovy paste"],
    "rice-wine": ["rice wine", "mirin", "sake"],
    "vinegar": ["balsamic vinegar", "apple cider vinegar", "rice vinegar", "vinegar"],
    "tomato-sauce": ["tomato paste", "tomato sauce", "crushed tomato", "diced tomato", "marinara"],
    "chicken-stock": ["chicken stock"],
    "beef-stock": ["beef stock"],
    "vegetable-stock": ["vegetable stock"],
    "stock": ["stock"],
    "chicken-broth": ["chicken broth"],
    "beef-broth": ["beef broth"],
    "vegetable-broth": ["vegetable broth"],
    "broth": ["broth"],
    "honey": ["honey"],
    "maple-syrup": ["maple syrup"],
    "sugar": ["brown sugar", "powdered sugar", "sugar"],
    "salt": ["salt"],
    "black-pepper": ["black pepper", "ground pepper", "pepper"],
}

# Pre-sort spellings longest-first for greedy matching
_FROZEN_INDEX: list[tuple[str, str]] = sorted(
    [
        (sp.lower().replace("-", " ").replace("_", " "), key)
        for key, spellings in _FROZEN_SPELLINGS.items()
        for sp in spellings
    ],
    key=lambda t: len(t[0]),
    reverse=True,
)
_FROZEN_CONSONANTS_BEFORE_Y = set("bcdfghjklmnpqrstvwxyz")


def _frozen_keys_for(name: str) -> set[str]:
    """Return ingredient keys whose spellings appear in name as whole words (frozen vocab)."""
    if not name:
        return set()
    cleaned = re.sub(r"[^\w\- ]", " ", name.lower().replace("-", " ").replace("_", " ").replace("&", " and "))
    padded = " " + " ".join(cleaned.split()) + " "
    found: set[str] = set()
    for spelling, key in _FROZEN_INDEX:
        if spelling.endswith("y") and len(spelling) >= 2 and spelling[-2] in _FROZEN_CONSONANTS_BEFORE_Y:
            pattern = re.compile(rf" {re.escape(spelling[:-1])}(?:y|ies) ")
        else:
            pattern = re.compile(rf" {re.escape(spelling)}(?:s|es)? ")
        if pattern.search(padded):
            found.add(key)
            padded = pattern.sub("  ", padded)
    return found


def upgrade() -> None:
    """Add taste_preferences and onboarded_at columns to users table, then fold old lists."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('taste_preferences', sa.JSON(), nullable=False, server_default='{}')
        )
        batch_op.add_column(
            sa.Column('onboarded_at', sa.DateTime(), nullable=True)
        )

    # Data migration: fold favorite_ingredients → love, disliked_ingredients → never.
    # _frozen_keys_for() is used instead of a live import so a future vocabulary
    # change in src/services/ingredient_keys.py cannot alter how existing rows
    # were backfilled.
    connection = op.get_bind()
    metadata = MetaData()
    users_table = Table('users', metadata, autoload_with=connection)

    rows = connection.execute(
        sa.select(
            users_table.c.id,
            users_table.c.favorite_ingredients,
            users_table.c.disliked_ingredients,
            users_table.c.created_at,
        )
    ).fetchall()

    for row in rows:
        prefs: dict[str, str] = {}

        # SQLite stores JSON as text; handle both serialised strings and Python lists.
        fav = row.favorite_ingredients
        if isinstance(fav, str):
            fav = json.loads(fav) if fav else []
        disliked = row.disliked_ingredients
        if isinstance(disliked, str):
            disliked = json.loads(disliked) if disliked else []

        for name in (fav or []):
            for key in _frozen_keys_for(name):
                prefs[f"ingredient:{key}"] = "love"

        for name in (disliked or []):
            for key in _frozen_keys_for(name):
                # love wins: if same key appears in both lists, keep "love"
                pref_key = f"ingredient:{key}"
                if pref_key not in prefs:
                    prefs[pref_key] = "never"

        connection.execute(
            users_table.update()
            .where(users_table.c.id == row.id)
            .values(taste_preferences=prefs, onboarded_at=row.created_at)
        )


def downgrade() -> None:
    """Remove taste_preferences and onboarded_at columns from users table."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('onboarded_at')
        batch_op.drop_column('taste_preferences')
