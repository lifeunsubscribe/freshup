"""Tests for the canonical ingredient key vocabulary."""

from types import SimpleNamespace

import pytest

from src.services.ingredient_keys import (
    ALLERGENS,
    INGREDIENTS,
    allergens_for,
    keys_for,
    keys_for_recipe,
    label_for,
)
from src.services.recipe_themes import VALUE_LABELS


# ---------------------------------------------------------------------------
# keys_for: basic mapping
# ---------------------------------------------------------------------------


class TestKeysFor:
    def test_bare_chicken_name(self):
        assert "chicken" in keys_for("chicken breast")

    def test_full_ingredient_string_chicken(self):
        assert "chicken" in keys_for("2 boneless chicken breasts")

    def test_broccoli_florets(self):
        assert "broccoli" in keys_for("broccoli florets")

    def test_beef(self):
        assert "beef" in keys_for("ground beef")

    def test_shrimp(self):
        assert "shrimp" in keys_for("shrimp")

    def test_salmon(self):
        assert "salmon" in keys_for("salmon fillet")

    def test_egg(self):
        assert "egg" in keys_for("2 large eggs")

    def test_butter(self):
        assert "butter" in keys_for("unsalted butter")

    def test_garlic(self):
        assert "garlic" in keys_for("garlic cloves")

    def test_onion(self):
        assert "onion" in keys_for("yellow onion")

    def test_tomato(self):
        assert "tomato" in keys_for("cherry tomatoes")

    def test_rice(self):
        assert "rice" in keys_for("jasmine rice")

    def test_pasta(self):
        assert "pasta" in keys_for("penne pasta")

    def test_tofu(self):
        assert "tofu" in keys_for("extra-firm tofu")

    def test_mushrooms(self):
        assert "mushrooms" in keys_for("sliced cremini mushrooms")

    def test_potato(self):
        assert "potatoes" in keys_for("russet potato")

    def test_lentils(self):
        assert "beans-legumes" in keys_for("red lentils")

    def test_chickpeas(self):
        assert "beans-legumes" in keys_for("canned chickpeas")

    def test_lamb(self):
        assert "lamb" in keys_for("lamb chops")

    def test_pork(self):
        assert "pork" in keys_for("pork loin")

    # --- Longest-match cases required by the issue ---

    def test_sweet_potato_not_potato(self):
        """'sweet potato' maps to sweet-potato, not potatoes."""
        result = keys_for("sweet potato wedges")
        assert "sweet-potato" in result
        assert "potatoes" not in result

    def test_green_beans_not_beans(self):
        """'green beans' maps to green-beans, not beans-legumes."""
        result = keys_for("green beans")
        assert "green-beans" in result
        assert "beans-legumes" not in result

    def test_peanut_butter_is_peanut(self):
        """'peanut butter' maps to peanut (not butter)."""
        result = keys_for("peanut butter sauce")
        assert "peanut" in result
        assert "butter" not in result

    def test_coconut_milk_is_coconut_not_milk(self):
        """'coconut milk' maps to coconut, not milk."""
        result = keys_for("coconut milk")
        assert "coconut" in result
        assert "milk" not in result

    # --- Edge cases ---

    def test_empty_string_returns_empty(self):
        assert keys_for("") == set()

    def test_none_returns_empty(self):
        assert keys_for(None) == set()

    def test_unknown_ingredient_returns_empty(self):
        assert keys_for("xyloberrinium extract") == set()

    def test_no_raises_on_garbage_input(self):
        # Must not raise
        result = keys_for("!!! ??? ###")
        assert isinstance(result, set)

    def test_plurals_accepted(self):
        assert "egg" in keys_for("eggs")
        assert "mushrooms" in keys_for("mushroom")

    def test_multiple_keys_in_one_string(self):
        result = keys_for("chicken breast with broccoli")
        assert "chicken" in result
        assert "broccoli" in result

    def test_anchovies_ies_plural(self):
        """Consonant+y words must match -ies plural form."""
        assert "anchovy" in keys_for("2 anchovies")

    def test_sardines_es_plural(self):
        """Non-y words still match via s/es suffix."""
        assert "sardine" in keys_for("canned sardines")

    def test_turkey_s_plural_unbroken(self):
        """Vowel+y words (turkey) still use regular s plural, not -ies."""
        result = keys_for("roasted turkeys")
        assert "turkey" in result

    def test_edamame_maps_to_edamame_key(self):
        assert "edamame" in keys_for("edamame")

    def test_edamame_not_beans_legumes(self):
        """Edamame has its own key separate from beans-legumes."""
        result = keys_for("edamame")
        assert "edamame" in result
        assert "beans-legumes" not in result

    def test_coconut_aminos_maps_to_own_key(self):
        result = keys_for("coconut aminos")
        assert "coconut-aminos" in result
        assert "soy-sauce" not in result


# ---------------------------------------------------------------------------
# allergens_for: allergen grouping
# ---------------------------------------------------------------------------


class TestAllergenMapping:
    def test_peanut_shrimp(self):
        """Canonical example from acceptance criteria."""
        result = allergens_for({"peanut", "shrimp"})
        assert result == {"peanut", "shellfish"}

    def test_milk_allergen(self):
        assert "milk" in allergens_for({"milk"})
        assert "milk" in allergens_for({"butter"})
        assert "milk" in allergens_for({"cheese"})

    def test_egg_allergen(self):
        assert "egg" in allergens_for({"egg"})

    def test_wheat_allergen(self):
        assert "wheat" in allergens_for({"wheat"})
        assert "wheat" in allergens_for({"pasta"})
        assert "wheat" in allergens_for({"bread"})

    def test_fish_allergen(self):
        assert "fish" in allergens_for({"salmon"})
        assert "fish" in allergens_for({"tuna"})

    def test_shellfish_allergen(self):
        assert "shellfish" in allergens_for({"crab"})
        assert "shellfish" in allergens_for({"lobster"})

    def test_soy_allergen(self):
        assert "soy" in allergens_for({"tofu"})
        assert "soy" in allergens_for({"soy-sauce"})
        assert "soy" in allergens_for({"edamame"})

    def test_seafood_triggers_fish_and_shellfish(self):
        """'seafood' key must trigger both fish and shellfish allergens."""
        result = allergens_for({"seafood"})
        assert "fish" in result
        assert "shellfish" in result

    def test_coconut_aminos_no_soy_allergen(self):
        """Coconut aminos is soy-free; must not trigger soy allergen."""
        result = allergens_for(keys_for("coconut aminos"))
        assert "soy" not in result

    def test_anchovies_triggers_fish_allergen(self):
        """anchovies (plural) must map through anchovy → fish allergen."""
        result = allergens_for(keys_for("2 anchovies"))
        assert "fish" in result

    def test_tree_nut_allergen(self):
        assert "tree-nut" in allergens_for({"almond"})
        assert "tree-nut" in allergens_for({"walnut"})

    def test_sesame_allergen(self):
        assert "sesame" in allergens_for({"sesame"})

    def test_empty_keys_returns_empty(self):
        assert allergens_for(set()) == set()

    def test_unknown_key_returns_no_allergen(self):
        assert allergens_for({"xyloberrinium"}) == set()


# ---------------------------------------------------------------------------
# Structural integrity: ALLERGENS keys are all in INGREDIENTS
# ---------------------------------------------------------------------------


class TestAllergenKeysExistInIngredients:
    def test_every_allergen_key_is_in_ingredients(self):
        missing = []
        for allergen, allergen_keys in ALLERGENS.items():
            for key in allergen_keys:
                if key not in INGREDIENTS:
                    missing.append((allergen, key))
        assert missing == [], f"Allergen keys not found in INGREDIENTS: {missing}"


# ---------------------------------------------------------------------------
# Structural integrity: VALUE_LABELS["ingredient"] food keys are in INGREDIENTS
# ---------------------------------------------------------------------------


class TestValueLabelsIngredientCoverage:
    def test_every_value_labels_ingredient_key_is_in_ingredients(self):
        missing = []
        for key in VALUE_LABELS["ingredient"]:
            if key not in INGREDIENTS:
                missing.append(key)
        assert missing == [], f"VALUE_LABELS ingredient keys missing from INGREDIENTS: {missing}"


# ---------------------------------------------------------------------------
# keys_for_recipe
# ---------------------------------------------------------------------------


class TestKeysForRecipe:
    def _make_recipe(self, ingredient_names):
        return SimpleNamespace(
            ingredients=[SimpleNamespace(ingredient_name=n) for n in ingredient_names]
        )

    def test_unions_all_ingredients(self):
        recipe = self._make_recipe(["boneless chicken breast", "broccoli florets"])
        result = keys_for_recipe(recipe)
        assert "chicken" in result
        assert "broccoli" in result

    def test_empty_ingredients(self):
        recipe = SimpleNamespace(ingredients=[])
        assert keys_for_recipe(recipe) == set()

    def test_none_ingredients(self):
        recipe = SimpleNamespace(ingredients=None)
        assert keys_for_recipe(recipe) == set()


# ---------------------------------------------------------------------------
# label_for
# ---------------------------------------------------------------------------


class TestLabelFor:
    def test_known_key_returns_label(self):
        assert label_for("chicken") == "Chicken"
        assert label_for("sweet-potato") == "Sweet potato"
        assert label_for("beans-legumes") == "Beans & legumes"

    def test_unknown_key_returns_key(self):
        assert label_for("unknown-ingredient") == "unknown-ingredient"


# ---------------------------------------------------------------------------
# Coverage: at least 60 entries in INGREDIENTS
# ---------------------------------------------------------------------------


class TestIngredientsCoverage:
    def test_at_least_60_ingredients(self):
        assert len(INGREDIENTS) >= 60, (
            f"INGREDIENTS has only {len(INGREDIENTS)} entries; at least 60 required"
        )
