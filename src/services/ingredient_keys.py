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

Compound products are their own ingredients. Coconut milk is neither coconut
nor milk; it is coconut milk, with its own key and its own allergens. So are
soy milk (soy, not dairy), fish sauce (fish), peanut butter, cream cheese,
rice noodles (no wheat), lemon juice (not lemon) and chicken stock (not broth,
and not chicken). A compound never resolves to one of its words: that
is how a dairy-free product gets flagged as milk and how fish sauce gets
missed. When adding an ingredient whose name contains another ingredient's
name, give it its own key and list its allergens in ALLERGENS explicitly.
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
    "tortilla": ("Tortilla", ["flour tortilla", "tortilla"]),
    "corn-tortilla": ("Corn tortilla", ["corn tortilla"]),
    "rice-noodles": ("Rice noodles", ["rice noodle", "rice vermicelli", "rice stick"]),
    "wheat": ("Wheat", ["flour", "wheat", "all-purpose flour", "whole wheat flour"]),
    # --- Produce: starchy vegetables ---
    "sweet-potato": ("Sweet potato", ["sweet potato"]),
    "potatoes": ("Potatoes", ["potato", "mashed potato", "yukon gold", "russet potato"]),
    "corn": ("Corn", ["corn", "maize"]),
    "cornstarch": ("Cornstarch", ["cornstarch", "corn starch"]),
    "potato-starch": ("Potato starch", ["potato starch"]),
    # --- Produce: non-starchy vegetables ---
    "broccoli": ("Broccoli", ["broccolini", "broccoli"]),
    "cauliflower": ("Cauliflower", ["cauliflower"]),
    "spinach": ("Spinach", ["spinach"]),
    "kale": ("Kale", ["kale"]),
    "cabbage": ("Cabbage", ["bok choy", "cabbage", "napa cabbage"]),
    "lettuce": ("Lettuce", ["romaine", "arugula", "lettuce"]),
    "tomato": ("Tomato", ["cherry tomato", "grape tomato", "roma tomato", "tomato"]),
    "pepper": ("Bell pepper", ["bell pepper", "red bell pepper", "green bell pepper", "red pepper",
                           "green pepper", "yellow pepper"]),
    "chili-flakes": ("Chili flakes", ["red pepper flake", "crushed red pepper", "chili flake",
                                      "chilli flake"]),
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
    "lemon": ("Lemon", ["lemon"]),
    "lemon-juice": ("Lemon juice", ["lemon juice"]),
    "lemon-zest": ("Lemon zest", ["lemon zest"]),
    "lime": ("Lime", ["lime"]),
    "lime-juice": ("Lime juice", ["lime juice"]),
    "lime-zest": ("Lime zest", ["lime zest"]),
    "avocado": ("Avocado", ["avocado"]),
    "apple": ("Apple", ["apple"]),
    "mango": ("Mango", ["mango"]),
    # --- Dairy & eggs ---
    "milk": ("Milk", ["whole milk", "skim milk", "milk"]),
    "coconut": ("Coconut", ["shredded coconut", "coconut flake", "coconut"]),
    "coconut-milk": ("Coconut milk", ["coconut milk"]),
    "coconut-cream": ("Coconut cream", ["coconut cream"]),
    "coconut-oil": ("Coconut oil", ["coconut oil"]),
    "almond-milk": ("Almond milk", ["almond milk"]),
    "soy-milk": ("Soy milk", ["soy milk", "soymilk"]),
    "oat-milk": ("Oat milk", ["oat milk"]),
    "cashew-cream": ("Cashew cream", ["cashew cream", "cashew milk"]),
    "buttermilk": ("Buttermilk", ["buttermilk"]),
    "cream": ("Cream", ["heavy cream", "whipping cream", "cream"]),
    "sour-cream": ("Sour cream", ["sour cream"]),
    "cream-cheese": ("Cream cheese", ["cream cheese"]),
    "butter": ("Butter", ["butter"]),
    "cheese": ("Cheese", [
        "mozzarella", "cheddar", "parmesan", "feta", "brie", "gouda", "ricotta",
        "gruyere", "cotija", "monterey jack", "cheese",
    ]),
    "yogurt": ("Yogurt", ["greek yogurt", "yogurt"]),
    "egg": ("Egg", ["egg white", "egg yolk", "egg"]),
    # --- Nuts & seeds ---
    "peanut": ("Peanut", ["peanut"]),
    "peanut-butter": ("Peanut butter", ["peanut butter"]),
    "peanut-oil": ("Peanut oil", ["peanut oil"]),
    "almond": ("Almond", ["almond"]),
    "almond-butter": ("Almond butter", ["almond butter"]),
    "walnut": ("Walnut", ["walnut"]),
    "pecan": ("Pecan", ["pecan"]),
    "cashew": ("Cashew", ["cashew"]),
    "pine-nut": ("Pine nut", ["pine nut"]),
    "pistachio": ("Pistachio", ["pistachio"]),
    "sesame": ("Sesame", ["sesame seed", "sesame"]),
    "sesame-oil": ("Sesame oil", ["toasted sesame oil", "sesame oil"]),
    "tahini": ("Tahini", ["tahini"]),
    "sunflower-seed": ("Sunflower seed", ["sunflower seed"]),
    "flaxseed": ("Flaxseed", ["flaxseed", "flax seed"]),
    # --- Pantry ---
    "olive-oil": ("Olive oil", ["olive oil"]),
    "soy-sauce": ("Soy sauce", ["soy sauce", "tamari"]),
    "coconut-aminos": ("Coconut aminos", ["coconut aminos"]),
    "fish-sauce": ("Fish sauce", ["fish sauce"]),
    "oyster-sauce": ("Oyster sauce", ["oyster sauce"]),
    "worcestershire": ("Worcestershire sauce", ["worcestershire sauce", "worcestershire"]),
    "shrimp-paste": ("Shrimp paste", ["shrimp paste"]),
    "anchovy-paste": ("Anchovy paste", ["anchovy paste"]),
    "rice-wine": ("Rice wine", ["rice wine", "mirin", "sake"]),
    "vinegar": ("Vinegar", ["balsamic vinegar", "apple cider vinegar", "rice vinegar", "vinegar"]),
    "tomato-sauce": ("Tomato sauce", ["tomato paste", "tomato sauce", "crushed tomato",
                                       "diced tomato", "marinara"]),
    # Stock and broth are different products, and so is each kind of either.
    "chicken-stock": ("Chicken stock", ["chicken stock"]),
    "beef-stock": ("Beef stock", ["beef stock"]),
    "vegetable-stock": ("Vegetable stock", ["vegetable stock"]),
    "stock": ("Stock", ["stock"]),
    "chicken-broth": ("Chicken broth", ["chicken broth"]),
    "beef-broth": ("Beef broth", ["beef broth"]),
    "vegetable-broth": ("Vegetable broth", ["vegetable broth"]),
    "broth": ("Broth", ["broth"]),
    "honey": ("Honey", ["honey"]),
    "maple-syrup": ("Maple syrup", ["maple syrup"]),
    "sugar": ("Sugar", ["brown sugar", "powdered sugar", "sugar"]),
    "salt": ("Salt", ["salt"]),
    # Bare "pepper" in a recipe ("salt and pepper") is the spice, not the vegetable.
    "black-pepper": ("Black pepper", ["black pepper", "ground pepper", "pepper"]),
}

# allergen name -> set of ingredient keys that contain that allergen
ALLERGENS: dict[str, set[str]] = {
    "milk": {"milk", "cream", "butter", "cheese", "yogurt", "buttermilk", "sour-cream", "cream-cheese"},
    "egg": {"egg"},
    "peanut": {"peanut", "peanut-butter", "peanut-oil"},
    "tree-nut": {"almond", "walnut", "pecan", "cashew", "pine-nut", "pistachio",
                 "almond-milk", "almond-butter", "cashew-cream"},
    "fish": {"salmon", "white-fish", "tuna", "anchovy", "sardine", "seafood",
             "fish-sauce", "worcestershire", "anchovy-paste"},
    "shellfish": {"shrimp", "crab", "lobster", "clam", "oyster", "scallop", "seafood",
                  "oyster-sauce", "shrimp-paste"},
    "wheat": {"wheat", "pasta", "bread", "couscous", "tortilla"},
    "soy": {"tofu", "soy-sauce", "edamame", "soy-milk"},
    "sesame": {"sesame", "sesame-oil", "tahini"},
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
