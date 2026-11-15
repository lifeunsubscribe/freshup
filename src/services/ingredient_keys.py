"""
Canonical ingredient vocabulary for FreshUp.

Turns free-text ingredient names into stable keys and groups those keys under
allergen categories. Keys that exist in VALUE_LABELS["ingredient"] reuse the
same string so callers can compare across both modules without mapping.

Matching rules (same as card_tags._match):
- Whole-word only (regex word boundaries via padding with spaces)
- Plural-tolerant: trailing s/es accepted
- Longest spelling first, matched span is blanked so multi-word phrases like
  "sweet potato" are not also counted as "potato"
"""

import re
from typing import Optional

from src.services.recipe_themes import normalize_tag


# key -> (display label, spellings)
# Spellings are matched longest-first; multi-word spellings must come before
# their component words when both would otherwise match.
INGREDIENTS: dict[str, tuple[str, list[str]]] = {
    # --- Proteins: poultry ---
    "chicken": ("Chicken", ["chicken breast", "chicken thigh", "chicken wing", "chicken", "poultry"]),
    "turkey": ("Turkey", ["turkey"]),
    "duck": ("Duck", ["duck"]),
    # --- Proteins: red meat ---
    "beef": ("Beef", ["ground beef", "beef", "steak", "sirloin", "ribeye", "flank steak", "brisket", "chuck"]),
    "pork": ("Pork", ["pork loin", "pork chop", "pork belly", "pork", "ham", "prosciutto", "pancetta"]),
    "lamb": ("Lamb", ["lamb chop", "lamb", "mutton"]),
    "veal": ("Veal", ["veal"]),
    # --- Proteins: seafood ---
    "salmon": ("Salmon", ["salmon"]),
    "shrimp": ("Shrimp", ["shrimp", "prawn"]),
    "white-fish": ("White fish", ["tilapia", "cod", "haddock", "catfish", "barramundi", "halibut", "flounder"]),
    "tuna": ("Tuna", ["tuna"]),
    "crab": ("Crab", ["crab"]),
    "lobster": ("Lobster", ["lobster"]),
    "clam": ("Clam", ["clam"]),
    "oyster": ("Oyster", ["oyster"]),
    "scallop": ("Scallop", ["scallop"]),
    "anchovy": ("Anchovy", ["anchovy"]),
    "sardine": ("Sardine", ["sardine"]),
    "seafood": ("Seafood", ["seafood"]),
    # --- Proteins: plant ---
    "tofu": ("Tofu", ["tofu", "tempeh"]),
    "sausage": ("Sausage", ["sausage", "chorizo", "bratwurst", "kielbasa"]),
    "bacon": ("Bacon", ["bacon"]),
    # --- Legumes ---
    "beans-legumes": ("Beans & legumes", [
        "black bean", "kidney bean", "pinto bean", "cannellini bean", "navy bean",
        "chickpea", "lentil", "pea", "split pea", "bean", "legume",
    ]),
    "edamame": ("Edamame", ["edamame", "soybean", "soy bean"]),
    # --- Grains ---
    "grains": ("Grains", ["quinoa", "farro", "barley", "millet", "bulgur", "oat", "grain"]),
    "rice": ("Rice", ["brown rice", "jasmine rice", "basmati rice", "arborio rice", "fried rice",
                      "risotto rice", "rice"]),
    "pasta": ("Pasta", ["pasta", "spaghetti", "penne", "fettuccine", "linguine", "rigatoni",
                         "fusilli", "orzo", "noodle"]),
    "bread": ("Bread", ["sourdough", "baguette", "naan", "pita", "flatbread", "brioche", "bread"]),
    "couscous": ("Couscous", ["couscous"]),
    "tortilla": ("Tortilla", ["tortilla"]),
    "wheat": ("Wheat", ["flour", "wheat", "all-purpose flour", "whole wheat flour"]),
    # --- Produce: starchy vegetables ---
    "sweet-potato": ("Sweet potato", ["sweet potato"]),
    "potatoes": ("Potatoes", ["potato", "mashed potato", "yukon gold", "russet potato"]),
    "corn": ("Corn", ["corn", "maize"]),
    # --- Produce: non-starchy vegetables ---
    "broccoli": ("Broccoli", ["broccolini", "broccoli"]),
    "cauliflower": ("Cauliflower", ["cauliflower"]),
    "spinach": ("Spinach", ["spinach"]),
    "kale": ("Kale", ["kale"]),
    "cabbage": ("Cabbage", ["bok choy", "cabbage", "napa cabbage"]),
    "lettuce": ("Lettuce", ["romaine", "arugula", "lettuce"]),
    "tomato": ("Tomato", ["cherry tomato", "grape tomato", "roma tomato", "tomato"]),
    "pepper": ("Bell pepper", ["bell pepper", "red pepper", "green pepper", "yellow pepper", "pepper"]),
    "onion": ("Onion", ["red onion", "yellow onion", "white onion", "green onion", "scallion",
                         "shallot", "leek", "onion"]),
    "garlic": ("Garlic", ["garlic"]),
    "carrot": ("Carrot", ["carrot"]),
    "celery": ("Celery", ["celery"]),
    "zucchini": ("Zucchini", ["zucchini", "courgette"]),
    "eggplant": ("Eggplant", ["eggplant", "aubergine"]),
    "asparagus": ("Asparagus", ["asparagus"]),
    "green-beans": ("Green beans", ["green bean", "green beans", "haricot vert"]),
    "mushrooms": ("Mushrooms", ["portobello", "cremini", "shiitake", "oyster mushroom",
                                 "mushroom"]),
    "cucumber": ("Cucumber", ["cucumber"]),
    "artichoke": ("Artichoke", ["artichoke"]),
    # --- Produce: fruit ---
    "lemon": ("Lemon", ["lemon", "lemon zest", "lemon juice"]),
    "lime": ("Lime", ["lime", "lime juice"]),
    "avocado": ("Avocado", ["avocado"]),
    "apple": ("Apple", ["apple"]),
    "mango": ("Mango", ["mango"]),
    # --- Dairy & eggs ---
    "milk": ("Milk", ["whole milk", "skim milk", "milk"]),
    "coconut": ("Coconut", ["coconut milk", "coconut cream", "shredded coconut",
                             "coconut flake", "coconut"]),
    "cream": ("Cream", ["heavy cream", "sour cream", "cream cheese", "cream"]),
    "butter": ("Butter", ["butter"]),
    "cheese": ("Cheese", [
        "mozzarella", "cheddar", "parmesan", "feta", "brie", "gouda", "ricotta",
        "gruyere", "cotija", "monterey jack", "cream cheese", "cheese",
    ]),
    "yogurt": ("Yogurt", ["greek yogurt", "yogurt"]),
    "egg": ("Egg", ["egg white", "egg yolk", "egg"]),
    # --- Nuts & seeds ---
    "peanut": ("Peanut", ["peanut butter", "peanut"]),
    "almond": ("Almond", ["almond milk", "almond butter", "almond"]),
    "walnut": ("Walnut", ["walnut"]),
    "pecan": ("Pecan", ["pecan"]),
    "cashew": ("Cashew", ["cashew"]),
    "pine-nut": ("Pine nut", ["pine nut"]),
    "pistachio": ("Pistachio", ["pistachio"]),
    "sesame": ("Sesame", ["tahini", "sesame oil", "sesame seed", "sesame"]),
    "sunflower-seed": ("Sunflower seed", ["sunflower seed"]),
    "flaxseed": ("Flaxseed", ["flaxseed", "flax seed"]),
    # --- Pantry ---
    "olive-oil": ("Olive oil", ["olive oil"]),
    "soy-sauce": ("Soy sauce", ["soy sauce", "tamari"]),
    "coconut-aminos": ("Coconut aminos", ["coconut aminos"]),
    "vinegar": ("Vinegar", ["balsamic vinegar", "apple cider vinegar", "rice vinegar", "vinegar"]),
    "tomato-sauce": ("Tomato sauce", ["tomato paste", "tomato sauce", "crushed tomato",
                                       "diced tomato", "marinara"]),
    "broth": ("Broth", ["chicken broth", "beef broth", "vegetable broth",
                         "chicken stock", "beef stock", "vegetable stock", "broth", "stock"]),
    "honey": ("Honey", ["honey"]),
    "maple-syrup": ("Maple syrup", ["maple syrup"]),
    "sugar": ("Sugar", ["brown sugar", "powdered sugar", "sugar"]),
    "salt": ("Salt", ["salt"]),
    "black-pepper": ("Black pepper", ["black pepper"]),
}

# allergen name -> set of ingredient keys that contain that allergen
ALLERGENS: dict[str, set[str]] = {
    "milk": {"milk", "cream", "butter", "cheese", "yogurt"},
    "egg": {"egg"},
    "peanut": {"peanut"},
    "tree-nut": {"almond", "walnut", "pecan", "cashew", "pine-nut", "pistachio"},
    "fish": {"salmon", "white-fish", "tuna", "anchovy", "sardine", "seafood"},
    "shellfish": {"shrimp", "crab", "lobster", "clam", "oyster", "scallop", "seafood"},
    "wheat": {"wheat", "pasta", "bread", "couscous", "tortilla"},
    "soy": {"tofu", "soy-sauce", "edamame"},
    "sesame": {"sesame"},
}

# pre-build: sorted spellings longest-first per key, normalised
_SPELLING_INDEX: list[tuple[str, str]] = sorted(
    [
        (normalize_tag(spelling), key)
        for key, (_, spellings) in INGREDIENTS.items()
        for spelling in spellings
    ],
    key=lambda t: len(t[0]),
    reverse=True,
)


def keys_for(name: Optional[str]) -> set[str]:
    """
    Return ingredient keys whose spellings appear in name as whole words.

    Longest spellings win: 'sweet potato' matches sweet-potato, not potatoes.
    Unknown names return an empty set; never raises.
    """
    if not name:
        return set()
    padded = " " + normalize_tag(re.sub(r"[^\w\- ]", " ", name)) + " "
    _consonants_before_y = set("bcdfghjklmnpqrstvwxyz")
    found: set[str] = set()
    for spelling, key in _SPELLING_INDEX:
        # Words ending in consonant+y form -ies plurals (anchovy→anchovies)
        if spelling.endswith("y") and len(spelling) >= 2 and spelling[-2] in _consonants_before_y:
            pattern = re.compile(rf" {re.escape(spelling[:-1])}(?:y|ies) ")
        else:
            pattern = re.compile(rf" {re.escape(spelling)}(?:s|es)? ")
        if pattern.search(padded):
            found.add(key)
            padded = pattern.sub("  ", padded)
    return found


def keys_for_recipe(recipe) -> set[str]:
    """Return the union of keys_for over every ingredient_name in recipe.ingredients."""
    result: set[str] = set()
    for ing in recipe.ingredients or []:
        result |= keys_for(getattr(ing, "ingredient_name", None))
    return result


def label_for(key: str) -> str:
    """Return the display label for a key, or the key itself if unknown."""
    entry = INGREDIENTS.get(key)
    return entry[0] if entry else key


def allergens_for(keys: set[str]) -> set[str]:
    """Return allergen names for the given set of ingredient keys."""
    return {allergen for allergen, allergen_keys in ALLERGENS.items() if allergen_keys & keys}
