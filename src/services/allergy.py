"""
What a user's allergy entries cover.

The profile's allergy field is free text: the user types whatever applies to
them. Each entry is read in this order:

1. A name for one of the major allergen groups in ingredient_keys.ALLERGENS
   ("milk", "dairy", "lactose", "tree nuts", "gluten", "shellfish"): the entry
   covers every ingredient in the group.
2. An ingredient in the vocabulary ("garlic", "coconut", "almonds"): the entry
   covers that ingredient, and the whole allergen group when the ingredient
   belongs to one. Almonds cover every tree nut; that is the cautious reading
   and the one allergists usually give.
3. Either way the entry also covers everything made from what it names
   (coconut covers coconut milk; chicken covers chicken stock).
4. Anything else ("mustard", "strawberries", "kiwi") is matched as a word
   against ingredient names, so an entry outside the vocabulary still blocks a
   recipe that lists it.

Known limits. A catalog card stores ingredient keys, not names, so rule 4 can
only read the card's name and headline. Sulphites cannot be inferred from an
ingredient list at all. Entries that are not foods match nothing.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

from src.services.ingredient_keys import ALLERGENS, allergens_for, keys_for, with_products
from src.services.recipe_themes import normalize_tag

_GLUTEN = ["wheat", "barley", "rye"]

# What people type -> allergen groups and ingredient keys. A name that is
# already a group ("milk") or that keys_for resolves ("almonds", "prawns")
# needs no entry.
_ALIASES: dict[str, list[str]] = {
    "dairy": ["milk"],
    "dairy product": ["milk"],
    "dairy products": ["milk"],
    "lactose": ["milk"],
    "casein": ["milk"],
    "whey": ["milk"],
    "milk protein": ["milk"],
    "eggs": ["egg"],
    "peanuts": ["peanut"],
    "groundnut": ["peanut"],
    "groundnuts": ["peanut"],
    "tree nut": ["tree-nut"],
    "tree nuts": ["tree-nut"],
    # "nuts" colloquially covers both tree nuts and peanuts
    "nut": ["tree-nut", "peanut"],
    "nuts": ["tree-nut", "peanut"],
    "soya": ["soy"],
    "soybean": ["soy"],
    "soybeans": ["soy"],
    "gluten": _GLUTEN,
    "celiac": _GLUTEN,
    "coeliac": _GLUTEN,
    "seafood": ["fish", "shellfish"],
    "crustacean": ["shellfish"],
    "crustaceans": ["shellfish"],
    "mollusc": ["shellfish"],
    "molluscs": ["shellfish"],
    "mollusk": ["shellfish"],
    "mollusks": ["shellfish"],
}

# Words around the food in an entry: "allergic to shellfish", "lactose intolerance", "gluten free".
_FILLER = re.compile(r"\b(?:allerg(?:y|ies|ic)|intoleran(?:ce|t)|sensitiv(?:e|ity)|free|to|no)\b")
# Entries that say there is no allergy.
_NOT_AN_ALLERGY = {"none", "n a", "na", "nil", "nothing"}

_CONSONANTS = set("bcdfghjklmnpqrstvwxyz")


def allergy_term(entry: object) -> str:
    """Return the food an entry names, normalised; "" when the entry names nothing."""
    term = normalize_tag(_FILLER.sub(" ", normalize_tag(re.sub(r"[^\w\- ]", " ", str(entry or "")))))
    return "" if term in _NOT_AN_ALLERGY else term


def stated_allergies(user) -> list[str]:
    """Return the user's allergy entries as terms, leaving out blank and "none" entries."""
    return [term for term in (allergy_term(a) for a in (user.allergies or [])) if term]


def allergy_keys(term: str) -> set[str]:
    """
    Return every ingredient key an allergy term covers.

    Empty when the term names nothing in the vocabulary; the caller then falls
    back to matching the term against ingredient names.
    """
    names = _ALIASES.get(term) or ([term] if term in ALLERGENS else None)
    if names is not None:
        keys: set[str] = set()
        for name in names:
            keys |= ALLERGENS.get(name, {name})
    else:
        keys = keys_for(term)
        for group in allergens_for(keys):
            keys |= ALLERGENS[group]
    return with_products(keys)


def _mentions(term: str, text: Optional[str]) -> bool:
    """True when text contains term as whole words, in singular or plural."""
    if not text:
        return False
    if term.endswith("ies"):
        stem, ending = term[:-3], "(?:y|ies)"
    elif len(term) >= 2 and term.endswith("y") and term[-2] in _CONSONANTS:
        stem, ending = term[:-1], "(?:y|ies)"
    elif term.endswith("oes"):
        stem, ending = term[:-2], "(?:s|es)?"
    elif term.endswith("s") and not term.endswith("ss"):
        stem, ending = term[:-1], "(?:s|es)?"
    else:
        stem, ending = term, "(?:s|es)?"
    padded = " " + normalize_tag(re.sub(r"[^\w\- ]", " ", text)) + " "
    return re.search(rf" {re.escape(stem)}{ending} ", padded) is not None


def allergy_hit(terms: Iterable[str], ingredient_keys: set[str], texts: Iterable[Optional[str]]) -> bool:
    """
    True when any allergy term covers one of ingredient_keys or, for a term
    outside the vocabulary, is named in one of texts.
    """
    texts = list(texts)
    for term in terms:
        covered = allergy_keys(term)
        if covered:
            if covered & ingredient_keys:
                return True
        elif any(_mentions(term, text) for text in texts):
            return True
    return False
