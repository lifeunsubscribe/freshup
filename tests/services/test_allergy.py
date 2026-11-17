"""
What a typed allergy entry covers (src/services/allergy.py).

The entries here are what people type into a free-text allergy field, checked
against ingredient lines as recipes write them.
"""

from types import SimpleNamespace

import pytest

from src.services.allergy import allergy_hit, allergy_keys, allergy_term, stated_allergies
from src.services.ingredient_keys import ALLERGENS, keys_for


def _blocks(entry: str, *ingredient_lines: str) -> bool:
    """Would this allergy entry block a recipe with these ingredient lines?"""
    keys: set[str] = set()
    for line in ingredient_lines:
        keys |= keys_for(line)
    return allergy_hit([allergy_term(entry)], keys, ingredient_lines)


class TestAllergyTerm:
    @pytest.mark.parametrize("entry, term", [
        ("Peanut", "peanut"),
        ("  tree nuts ", "tree nuts"),
        ("Tree-Nuts", "tree nuts"),
        ("Lactose intolerance", "lactose"),
        ("lactose intolerant", "lactose"),
        ("allergic to shellfish", "shellfish"),
        ("peanut allergy", "peanut"),
        ("gluten-free", "gluten"),
        ("no nuts", "nuts"),
    ])
    def test_reads_the_food_out_of_the_entry(self, entry, term):
        assert allergy_term(entry) == term

    @pytest.mark.parametrize("entry", ["", "   ", "none", "None", "N/A", "no allergies", None])
    def test_entries_that_name_no_allergy(self, entry):
        assert allergy_term(entry) == ""

    def test_stated_allergies_drops_blank_and_none_entries(self):
        user = SimpleNamespace(allergies=["", "none", " Garlic ", "N/A"])
        assert stated_allergies(user) == ["garlic"]

    def test_stated_allergies_with_no_field(self):
        assert stated_allergies(SimpleNamespace(allergies=None)) == []


class TestAllergenGroups:
    """An entry naming a major allergen covers every ingredient in the group."""

    @pytest.mark.parametrize("entry, group", [
        ("milk", "milk"), ("dairy", "milk"), ("lactose", "milk"), ("casein", "milk"),
        ("egg", "egg"), ("eggs", "egg"),
        ("peanut", "peanut"), ("peanuts", "peanut"),
        ("tree nut", "tree-nut"), ("tree nuts", "tree-nut"), ("tree-nut", "tree-nut"),
        ("fish", "fish"),
        ("shellfish", "shellfish"), ("crustaceans", "shellfish"), ("molluscs", "shellfish"),
        ("wheat", "wheat"),
        ("soy", "soy"), ("soya", "soy"), ("soybeans", "soy"),
        ("sesame", "sesame"),
    ])
    def test_group_names_and_aliases(self, entry, group):
        assert ALLERGENS[group] <= allergy_keys(allergy_term(entry))

    def test_nuts_covers_tree_nuts_and_peanuts(self):
        covered = allergy_keys("nuts")
        assert ALLERGENS["tree-nut"] <= covered and ALLERGENS["peanut"] <= covered

    def test_seafood_covers_fish_and_shellfish(self):
        covered = allergy_keys("seafood")
        assert ALLERGENS["fish"] <= covered and ALLERGENS["shellfish"] <= covered

    def test_gluten_covers_wheat_barley_and_rye(self):
        covered = allergy_keys("gluten")
        assert ALLERGENS["wheat"] <= covered
        assert {"barley", "rye"} <= covered
        assert "rice" not in covered and "grains" not in covered

    @pytest.mark.parametrize("entry, group", [
        ("almonds", "tree-nut"), ("cashew", "tree-nut"), ("hazelnuts", "tree-nut"),
        ("salmon", "fish"), ("prawns", "shellfish"), ("shrimp", "shellfish"),
        ("cheese", "milk"), ("butter", "milk"), ("tofu", "soy"), ("tahini", "sesame"),
    ])
    def test_an_ingredient_in_a_group_stands_for_the_group(self, entry, group):
        assert ALLERGENS[group] <= allergy_keys(allergy_term(entry))


class TestAnyIngredient:
    """An entry can be any ingredient, not only a major allergen."""

    @pytest.mark.parametrize("entry, line", [
        ("garlic", "3 cloves garlic, minced"),
        ("Garlic", "garlic powder"),
        ("mushrooms", "8 oz cremini mushrooms"),
        ("tomatoes", "1 can crushed tomatoes"),
        ("avocado", "2 ripe avocados"),
        ("corn", "1 tablespoon cornstarch"),
        ("celery", "2 stalks celery"),
    ])
    def test_blocks_a_recipe_that_lists_it(self, entry, line):
        assert _blocks(entry, line)

    @pytest.mark.parametrize("entry, line", [
        ("garlic", "1 yellow onion"),
        ("mushrooms", "oyster sauce"),
        ("corn", "black peppercorns"),
        ("tomatoes", "1 red bell pepper"),
    ])
    def test_does_not_block_other_ingredients(self, entry, line):
        assert not _blocks(entry, line)

    def test_an_ingredient_outside_the_groups_covers_only_itself_and_its_products(self):
        assert allergy_keys("garlic") == {"garlic"}
        assert allergy_keys("chicken") == {"chicken", "chicken-stock", "chicken-broth"}


class TestMadeFrom:
    """An allergy to an ingredient covers what is made from it, in one direction only."""

    @pytest.mark.parametrize("entry, line", [
        ("coconut", "1 can coconut milk"),
        ("coconut", "2 tablespoons coconut oil"),
        ("coconut", "coconut cream"),
        ("coconut", "coconut aminos"),
        ("lemon", "2 tablespoons lemon juice"),
        ("lime", "lime zest"),
        ("chicken", "2 cups chicken stock"),
        ("beef", "beef broth"),
        ("pork", "4 slices bacon"),
        ("rice", "rice noodles"),
        ("tomato", "2 tablespoons tomato paste"),
        ("anchovy", "fish sauce"),
        ("egg", "2 tablespoons mayonnaise"),
        ("wheat", "1/2 cup panko breadcrumbs"),
        ("wheat", "2 tablespoons soy sauce"),
        ("milk", "1 tablespoon ghee"),
    ])
    def test_source_covers_product(self, entry, line):
        assert _blocks(entry, line)

    @pytest.mark.parametrize("entry, line", [
        # The compound rule still holds: coconut milk is not milk, and so on.
        ("milk", "1 can coconut milk"),
        ("dairy", "oat milk"),
        ("lactose", "almond milk"),
        ("peanut", "coconut oil"),
        ("wheat", "rice noodles"),
        ("wheat", "corn tortillas"),
        ("fish", "oyster sauce"),
        # A product does not cover its source or its siblings.
        ("coconut milk", "shredded coconut"),
        ("coconut milk", "coconut oil"),
        ("lemon juice", "1 lemon"),
    ])
    def test_does_not_run_the_other_way(self, entry, line):
        assert not _blocks(entry, line)


class TestOutsideTheVocabulary:
    """A food the vocabulary has no key for is matched as a word in ingredient names."""

    @pytest.mark.parametrize("entry, line", [
        ("mustard", "1 tablespoon Dijon mustard"),
        ("strawberries", "1 cup strawberries, hulled"),
        ("strawberry", "fresh strawberries"),
        ("strawberries", "1 strawberry"),
        ("kiwi", "2 kiwis, peeled"),
        ("cilantro", "1/4 cup chopped cilantro"),
        ("bell peppers", "1 green bell pepper"),
    ])
    def test_blocks_a_recipe_that_names_it(self, entry, line):
        assert _blocks(entry, line)

    @pytest.mark.parametrize("entry, line", [
        ("mustard", "2 cups chicken stock"),
        ("kiwi", "1 lime"),
        ("penicillin", "penne pasta"),
        ("nutmeg", "1 cup walnuts"),
    ])
    def test_does_not_block_a_recipe_that_does_not(self, entry, line):
        assert not _blocks(entry, line)

    def test_whole_words_only(self):
        # "pea" must not match "peanut", and "nut" is an alias, not a substring test
        assert not allergy_hit(["kiw"], set(), ["2 kiwis"])
        assert not allergy_hit(["berry"], set(), ["strawberries"])

    def test_a_known_food_is_never_matched_as_a_word(self):
        # "milk" is in the vocabulary, so it is matched by key: the word "milk"
        # in "coconut milk" must not count.
        assert not allergy_hit(["milk"], keys_for("coconut milk"), ["coconut milk"])
