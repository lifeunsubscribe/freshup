# Encountered Issues (Needs Triage)

## Issues discovered during implementation of #301-302

- **2026-03-26** | `frontend/src/api/types.ts:304-313` | missing-feature | RecipeListResponse lacks ingredients field | Affects: Recipe cards in browse/carousel views cannot show "All in stock" badge | Fix: Add ingredients array to RecipeListResponse in backend, or add computed field `has_all_ingredients_in_stock` to avoid N+1 queries | Done: Recipe cards display "All in stock" badge when `allIngredientsInStock` prop is true, RecipeCarousel/RecipeGrid calculate stock status from ingredients
