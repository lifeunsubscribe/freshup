# FreshUp — Implementation Plan: Recipe Engagement & Personalized Feed

**Scope:** New feature area spanning data model changes, API endpoints, scraper architecture overhaul, personalized feed engine, and frontend updates.  
**Author:** Sarah + Claude (architecture session, 2026-05-03)  
**Status:** Approved — Ready for Sharkrite issue generation  
**Companion to:** `docs/FreshUp-ADR.md` (updated concurrently with this plan)  
**Disposition:** This file serves as the implementation reference for Sharkrite. Delete after all issues are closed.

---

## 0. Summary of Changes

This plan introduces the **Recipe Engagement & Personalized Feed** system — the features needed to make FreshUp a daily-use app where users browse, save, organize, cook, and rate recipes with a personalized home experience.

**What's changing:**

1. **Data model:** `UserRecipeRating` → `UserRecipeRelation` with bookmark/like/rating split. New `Menu` and `MenuRecipe` models. New `is_persisted` flag on `Recipe`. New `UserRecipeView` for view tracking.
2. **Scraper architecture:** Scrapers no longer bulk-insert into the Recipe table. They write to a browse cache (non-persisted recipes). Recipes persist only on user action (bookmark, like, or meal plan add).
3. **Personalized feed engine:** Per-user homepage with dynamic carousel rows derived from behavioral patterns. Deterministic SQL scoring recomputed on page load with short TTL cache.
4. **Menu system:** Auto-generated and user-created recipe collections with editable filter/organization rules.
5. **Meal plan draft generation:** Auto-draft weekly schedule for inspiration, with household vs. personal plan toggle and per-meal opt-out.
6. **Recipe card quick actions:** Inline bookmark, like, and add-to-plan buttons on all recipe surfaces.

**What's NOT changing:**

- Phase 3C Democratic Meal Planning voting flow (preserved as-is; the auto-draft feature introduced here is a lighter single-user precursor, not a replacement).
- Phase 3A Suggestion Engine priority queue (Section 5.2 — preserved; the personalized feed extends it with new signal types but doesn't replace the priority ordering).
- Existing Phase 1 backend APIs (inventory, grocery, prepared food — untouched).
- Design system color palette, typography, spacing rules (locked per `FreshUp-Design-System.md`).

---

## 1. Data Model Changes

### 1.1 Rename `UserRecipeRating` → `UserRecipeRelation`

**Current state:** `user_recipe_ratings` table with fields: `id`, `user_id`, `recipe_id`, `rating` (nullable float), `is_favorite` (bool), `notes`, `created_at`, `updated_at`.

**Target state:** `user_recipe_relations` table.

| Field | Type | Notes | Migration |
|---|---|---|---|
| id | UUID | PK | Keep |
| user_id | FK(users) | | Keep |
| recipe_id | FK(recipes) | | Keep |
| is_bookmarked | Boolean | Default false. "Save for later" — private utility. | New (migrate `is_favorite=true` → `is_bookmarked=true`) |
| is_liked | Boolean | Default false. "I endorse this" — public-facing curation, visible on user profile. | New (default false for all existing rows) |
| rating | Float? | 0.0–5.0. Nullable. **Gated:** API endpoint rejects rating submissions unless the user has at least one cook event logged for this recipe (checked via `UserCookEvent` or `times_cooked_by_user` — see 1.5). DB allows null freely for migration flexibility. | Keep |
| rating_photos | JSON? | Array of MinIO object keys for photos attached to the rating. Only accepted post-cook. | New |
| rating_comment | String(2000)? | User's post-cook commentary, tips, modifications. Replaces `notes` for rating-specific feedback. | New (migrate existing `notes` → `rating_comment`) |
| notes | String(1000)? | **Removed.** Migrated to `rating_comment`. | Drop after migration |
| menu_id | FK(menus)? | Default menu assignment on bookmark. Nullable (bookmarked but uncategorized). | New |
| created_at | DateTime | | Keep |
| updated_at | DateTime | | Keep |

**UniqueConstraint:** `(user_id, recipe_id)` — preserved, renamed to `uq_user_recipe_relation`.

**Migration instructions for Sharkrite/Mako:**
- Alembic migration with `render_as_batch=True` (SQLite).
- Rename table `user_recipe_ratings` → `user_recipe_relations`.
- Add columns `is_bookmarked`, `is_liked`, `rating_photos`, `rating_comment`, `menu_id`.
- Data migration: `UPDATE user_recipe_relations SET is_bookmarked = is_favorite`.
- Drop column `is_favorite`, `notes` (after data migration).
- Update all references: model class name, relationship names on `User` and `Recipe`, router imports, schema imports, test fixtures.
- The relationship on `User` changes from `recipe_ratings` → `recipe_relations`. The relationship on `Recipe` changes from `user_ratings` → `user_relations`.

### 1.2 New Model: `Menu`

User-created or system-generated recipe collections.

| Field | Type | Notes |
|---|---|---|
| id | UUID | PK |
| user_id | FK(users) | Owner |
| name | String(255) | Display name (user-editable). Auto-generated menus get descriptive defaults like "Indian cuisine" or "Quick weeknight meals". |
| description | String(500)? | Optional user description |
| filter_rules | JSON? | For auto-generated menus: the rules that populate and maintain the menu. Editable by user. Schema: `{"match": "all"|"any", "rules": [{"field": "tags", "op": "contains", "value": "indian"}, {"field": "cook_time_minutes", "op": "<=", "value": 30}]}`. Null for fully manual menus. |
| is_auto_generated | Boolean | True if system-created. Auto-generated menus can still be edited (title, rules, manual add/remove). |
| cover_image | String? | MinIO key. Defaults to first recipe's image. User can override. |
| sort_order | Integer | For ordering in the user's menu list and homepage rotation |
| created_at | DateTime | |
| updated_at | DateTime | |

**Filter rule schema detail:** Each rule specifies a `field` (recipe attribute to match), an `op` (operator), and a `value`. Supported fields and operators:

- `tags` — `contains`, `not_contains` (matches any tag in the recipe's tags array)
- `source_type` — `eq`, `in` (e.g., `"hellofresh_web"`, `["hellofresh_web", "hellofresh_card"]`)
- `cook_time_minutes` — `<=`, `>=`, `eq`
- `nutritional_info.calories` — `<=`, `>=` (requires non-null nutritional_info)
- `cuisine` — `eq`, `in` (derived from tags — e.g., a tag "indian" matches cuisine "indian")

`match: "all"` means AND logic across rules. `match: "any"` means OR logic.

When `filter_rules` is non-null, the menu auto-populates from the user's bookmarked + liked recipes that match the rules. Recipes manually added to the menu stay even if they don't match the filter. Recipes manually removed stay excluded even if they match.

### 1.3 New Model: `MenuRecipe` (Join Table)

| Field | Type | Notes |
|---|---|---|
| menu_id | FK(menus) | |
| recipe_id | FK(recipes) | |
| sort_order | Integer | Position within the menu |
| manually_added | Boolean | True if user explicitly added this recipe (immune to filter rule changes) |
| manually_removed | Boolean | True if user explicitly removed this recipe from an auto-generated menu (suppresses re-addition by filter rules) |
| added_at | DateTime | |

**Composite PK:** `(menu_id, recipe_id)`.

### 1.4 Recipe Model: Add `is_persisted` Flag

| Field | Type | Notes |
|---|---|---|
| is_persisted | Boolean | Default `true` for all existing recipes. Scraped/browsed recipes enter as `false`. Set to `true` when any user bookmarks, likes, or adds to meal plan. |

**Migration:** Add column with default `true` so all existing recipes are unaffected.

**Cleanup job:** A scheduled task prunes non-persisted recipes older than 7 days. This prevents the Recipe table from growing unboundedly with browse cache data. The TTL is configurable via `BROWSE_CACHE_TTL_DAYS` env var.

### 1.5 New Model: `UserCookEvent`

Tracks when a specific user cooks a specific recipe. Required for gating ratings.

| Field | Type | Notes |
|---|---|---|
| id | UUID | PK |
| user_id | FK(users) | |
| recipe_id | FK(recipes) | |
| cooked_at | DateTime | When the user cooked this recipe |
| meal_plan_entry_id | FK(meal_plan_entries)? | Link to the meal plan entry if applicable |
| notes | String(500)? | Optional cook notes |

**Relationship to `Recipe.times_cooked`:** `times_cooked` on Recipe is the global count (all users combined). `UserCookEvent` tracks per-user cook history. The rating gate checks: `SELECT COUNT(*) FROM user_cook_events WHERE user_id = :uid AND recipe_id = :rid` > 0.

**When cook events are created:**
- When a `MealPlanEntry` transitions to status `cooked` (Phase 3 — for now, a manual "I cooked this" button on the recipe detail page).
- Via a dedicated `POST /recipes/{id}/cook` endpoint for recipes cooked outside the meal plan.

### 1.6 New Model: `UserRecipeView`

Lightweight view tracking for the "viewed but not cooked" feed signal.

| Field | Type | Notes |
|---|---|---|
| id | UUID | PK |
| user_id | FK(users) | |
| recipe_id | FK(recipes) | |
| viewed_at | DateTime | |
| source | String(50)? | Where the view happened: `browse`, `detail`, `search`, `feed`, `menu`. For analytics. |

**No unique constraint** — one user can view the same recipe multiple times and each is recorded. The feed signal cares about view count relative to cook count.

---

## 2. Scraper Architecture Overhaul

### 2.1 Problem

Currently, scrapers (HelloFresh, Kitchen Sanctuary) bulk-insert recipes directly into the `recipes` table. Every scraped recipe becomes a permanent database entry regardless of whether anyone cares about it. This pollutes the database with potentially hundreds or thousands of recipes that were never viewed, bookmarked, or cooked.

### 2.2 New Architecture: Browse-Then-Persist

**Scraper behavior changes:**
- Scrapers still use the same `recipe-scrapers` library and the same crawling logic.
- Scraped recipes are inserted into the `recipes` table with `is_persisted = false`.
- The cleanup job (Section 1.4) prunes non-persisted recipes older than 7 days.
- Scrapers run periodically (configurable, default weekly) to refresh the browse cache.

**Persistence trigger:** When a user bookmarks, likes, or adds a recipe to a meal plan:
1. If the recipe has `is_persisted = false`, set `is_persisted = true`.
2. Create the `UserRecipeRelation` row.
3. The recipe is now permanent — it survives the cleanup job and accumulates ratings, cook events, etc.

**Frontend implications:**
- Recipe cards and detail pages look identical for persisted and non-persisted recipes. The user doesn't know or care about the distinction.
- The only user-facing difference: non-persisted recipes won't have household context data (times cooked, ratings, etc.) because nobody has interacted with them yet.

### 2.3 Cold Start: Empty Database Fallback

When the database has zero persisted recipes (or a specific user has zero saves), the system needs content to display.

**Strategy:**
- On first deploy or empty state, run the scrapers immediately to populate the browse cache.
- The homepage and recipe browse page query non-persisted recipes as fallback content when personalized rows have insufficient data.
- Fallback carousels are labeled generically: "Popular on HelloFresh.", "Quick weeknight meals.", "Try something new." — using metadata from the scraped recipes (tags, cook time, source) rather than personalization signals.
- As users save recipes, personalized rows phase in and generic rows phase out.

### 2.4 Existing Scraper Modifications

**Files affected:**
- `src/services/crawlers/hellofresh_crawler.py` — Add `is_persisted=False` to recipe creation.
- `src/services/crawlers/kitchen_sanctuary_crawler.py` — Same.
- `src/services/crawlers/base_crawler.py` — Add `is_persisted` parameter to base recipe creation method.
- `src/routers/scraper.py` — Ensure scraper endpoints set `is_persisted=False`.

**Deduplication update:** The existing dedup logic (don't re-import recipes already in the database) must now also account for `is_persisted` status. If a non-persisted recipe already exists and was pruned, the scraper can re-create it. If a persisted recipe exists, skip it as before.

---

## 3. Personalized Feed Engine

### 3.1 Architecture

The feed engine is a set of deterministic SQL queries that produce ordered recipe lists for each carousel row on the homepage and recipe browse page. No LLM involvement. Scoring is pure math + SQL aggregation.

**Compute model:** Recomputed on page load. React Query `staleTime` of 15 minutes provides the effective TTL cache — if the user navigates away and back within 15 minutes, the cached feed is shown without re-fetching.

**API endpoint:** `GET /feed/home` — returns the complete personalized homepage payload for the authenticated user. Response shape:

```json
{
  "make_now": [Recipe, ...],
  "on_repeat": [Recipe, ...],
  "personalized_rows": [
    {"title": "Indian cuisine.", "key": "tag:indian", "recipes": [Recipe, ...]},
    {"title": "From HelloFresh.", "key": "source:hellofresh_web", "recipes": [Recipe, ...]},
    {"title": "Quick meals.", "key": "cook_time:<=30", "recipes": [Recipe, ...]}
  ],
  "source_rows": [
    {"title": "HelloFresh.", "source_type": "hellofresh_web", "recipes": [Recipe, ...], "browse_url": "/recipes?source=hellofresh_web"}
  ],
  "fallback_rows": [
    {"title": "Popular recipes.", "recipes": [Recipe, ...]}
  ]
}
```

### 3.2 "Make This Right Now" Slideshow

**What it shows:** Recipes the user can cook immediately based on current inventory. Hero position on homepage.

**Query logic:**
1. Get all recipes where `is_persisted = true` (persisted recipes only for "make now" — these are recipes the household has intentionally saved).
2. For each recipe, compute ingredient availability: `COUNT(recipe_ingredients WHERE matching inventory_item exists AND quantity >= required) / COUNT(all recipe_ingredients)`.
3. Filter to recipes with 100% availability (or configurable threshold, e.g., >=80% with "missing 1 ingredient" label).
4. Sort by: freshness priority (ingredients closest to expiration first), then familiar-first (times_cooked DESC), then user preference (is_bookmarked or is_liked by this user).
5. Return top 10.

**Relationship to Section 5.2 Suggestion Engine:** This uses the same inventory-aware filtering as Phase 3A's Suggestion Engine but is a simpler, pre-Phase-3 implementation. When Phase 3A is built, the "Make This Right Now" query delegates to the Suggestion Engine's inventory filter. For now, it's a standalone query.

### 3.3 "On Repeat" Playlist

**What it shows:** Recipes the user is currently into — a blend of behavioral signals that surface what's top-of-mind.

**Signal sources (all per-user):**

1. **Viewed but not cooked** — Recipes with high `UserRecipeView` count relative to zero `UserCookEvent` entries. These are recipes the user keeps looking at but hasn't committed to. Weight: 0.25.
2. **High-frequency cooked** — Recipes with above-average `UserCookEvent` count for this user, biased toward recency (cook events in the last 30 days weighted 2x vs. older). Weight: 0.30.
3. **Recently highly rated** — Recipes the user rated >= 4.0 in the last 60 days. Weight: 0.25.
4. **Genre/ingredient affinity** — Recipes that share tags or key ingredients with the recipes in categories 1-3. This is the "you might also like" expansion. Weight: 0.20.

**Scoring formula:** For each candidate recipe, compute a weighted score across all applicable signals. Normalize each signal to 0-1 range before weighting. Deduplicate across signal sources (a recipe that appears in multiple signals gets the max score, not the sum — prevents double-counting).

**Output:** Top 15 recipes, shuffled lightly (top 5 are deterministic, positions 6-15 are randomized within score tiers to add variety).

### 3.4 Dynamic Personalized Rows

**What they show:** 3–4 carousel rows on the homepage driven by the user's strongest behavioral patterns across *any recipe attribute*.

**Pattern detection query:**
```sql
-- For each attribute type, find the user's top patterns
-- Attribute types: source_type, tags (each tag individually), cuisine (from tags)

-- Example: top source types by save count
SELECT r.source_type, COUNT(*) as save_count
FROM user_recipe_relations urr
JOIN recipes r ON urr.recipe_id = r.id
WHERE urr.user_id = :user_id
  AND (urr.is_bookmarked = true OR urr.is_liked = true)
GROUP BY r.source_type
ORDER BY save_count DESC
LIMIT 4;

-- Example: top tags by save count (tags is a JSON array, need to unnest)
-- Implementation varies by DB but the concept is: flatten tags, count per tag
```

**Row selection algorithm:**
1. Compute save counts for: each `source_type`, each unique tag, each `cook_time_minutes` bucket (<=15, <=30, <=45, <=60, >60).
2. Rank all patterns by save count across all attribute types.
3. Select top 3–4 patterns, preferring diversity (don't show two tag-based rows if a source-based row also ranks highly).
4. For each selected pattern, query the user's saved recipes matching that pattern + non-persisted recipes matching that pattern (to show new discoveries alongside saved favorites).

**Row titles:** Auto-generated from the pattern. `source_type: hellofresh_web` → "From HelloFresh." / `tag: indian` → "Indian cuisine." / `cook_time_minutes: <=30` → "Quick meals." Follow the design system's sentence case + olive period convention.

**Minimum threshold:** A pattern needs at least 3 saves to generate a row. Below that threshold, the slot is filled with a fallback row instead.

### 3.5 Source-Specific Rows

**What they show:** Dedicated rows for recipe sources the user engages with most. Distinct from personalized rows because they include an "expand into browse page" action.

**Shown when:** A source has >= 5 saved recipes from that user. Maximum 2 source rows on homepage.

**Browse page expansion:** Tapping "See all" on a source row navigates to the recipe browse page with `?source={source_type}` filter pre-applied. This page shows:
- All persisted recipes from that source (user's saves) at the top.
- Non-persisted (browse cache) recipes from that source below, under a "Discover more" divider.
- If the browse cache is thin, the page can trigger a targeted scraper run for that source (async, shows loading state).

### 3.6 Auto-Generated Menus

**What they are:** System-created recipe collections organized by the same pattern detection rules as personalized rows, but not limited to 3–4. All auto-generated menus are permanently accessible to the user in a "My Menus" section.

**Generation trigger:** Recomputed weekly (or on-demand when the user opens "My Menus"). Patterns with >= 3 saves get a menu.

**User editability (critical requirement):**
- **Title:** User can rename any auto-generated menu. Renamed menus keep their filter rules but use the custom title.
- **Filter rules:** User can edit the filter rules that define the menu. The rules UI exposes:
  - Add/remove attribute filters (e.g., change "Indian cuisine" to "Indian cuisine AND sides" by adding a tag filter for "side").
  - Change match logic (all/any).
  - Add calorie or cook time constraints.
  - Expand scope (e.g., change "Indian" to "Indian OR Asian" by switching to `match: any` and adding a second tag rule).
- **Manual overrides:** User can manually add recipes that don't match the filter (flagged as `manually_added=true` in `MenuRecipe`). User can manually remove recipes that do match the filter (flagged as `manually_removed=true`).
- **Once edited, `is_auto_generated` remains true** but the system respects manual overrides. The menu continues to auto-update as new recipes are saved that match the (possibly user-edited) rules.

**Homepage rotation:** Auto-generated menus rotate into homepage carousel slots. The rotation algorithm shows the 2–3 menus the user engages with most (measured by menu open count and recipe-from-menu cook count). Menus not rotated onto the homepage are still accessible in "My Menus."

### 3.7 Fallback Rows (Cold Start)

**When used:** When the user has insufficient save data to fill personalized rows (new user, or very few saves).

**Content:**
- "Popular recipes." — Top recipes by global `times_cooked` across all users.
- "Quick weeknight meals." — Recipes with `cook_time_minutes <= 30`, sorted by global popularity.
- "New in the kitchen." — Most recently scraped recipes from the browse cache.

**Phase-out:** As personalized rows fill in (user saves >= 3 recipes matching a pattern), fallback rows are displaced one-for-one. Homepage always shows exactly 3–4 content rows below "Make This Right Now" and "On Repeat," mixing personalized and fallback as needed.

---

## 4. Meal Plan Schedule & Auto-Draft

### 4.1 Weekly Auto-Draft

**What it does:** Each week (configurable day/time, default Sunday 8am), the system generates a draft weekly meal plan for inspiration. This is a *preview* — nothing is committed to the actual meal plan or grocery list.

**Draft generation logic:**
1. Pull from the Suggestion Engine priority queue (Section 5.2): expiring items first, then familiar recipes, then new suggestions.
2. Fill 7 dinner slots (one per day). Optionally fill lunch slots if the user has opted into lunch planning.
3. Weight by: variety (don't repeat cuisines on consecutive days), dietary balance, ingredient overlap (batch-friendly grouping reduces grocery trips).
4. Include 1–2 "stretch" recipes (from browse cache or lower-ranked saves) to introduce variety.

**User interaction:**
- Draft appears on the Plan page as a suggested schedule.
- Each slot shows the suggested recipe with a faded/greyed-out card treatment (per your spec — this indicates "draft, not confirmed").
- User can: accept a recipe (moves to confirmed status, becomes a normal card), swap it for another, dismiss it, or ignore the entire draft.
- **Only confirmed recipes** propagate to the grocery list. Draft recipes have zero impact on grocery list or inventory reservations.

### 4.2 Household vs. Personal Plan Toggle

**Behavior:** On the Plan page, a toggle switches between "Household plan" and "My plan" views.

- **Household plan:** Shows meals that have been confirmed by the coordinator (or by any household member for their assigned cooking days). All household members see the same schedule. This is the Phase 3C Democratic Meal Planning output when it's built; for now, it's the coordinator-confirmed schedule.
- **My plan:** Shows the user's personal meal schedule. Includes: household meals they've opted into, personal meals they've planned for themselves (e.g., lunches the household doesn't share), and their auto-draft suggestions.

**Visual treatment:**
- Confirmed household meals: full-color recipe cards with opt-in/opt-out toggle per meal.
- Confirmed personal meals: full-color recipe cards.
- Draft/suggested meals: faded/greyed-out recipe cards with accept/dismiss/swap actions. Clearly labeled "Suggested" or similar indicator.
- Opted-out meals: slot shows "You opted out" with a "Plan something" link to browse recipes.

### 4.3 Per-Meal Opt-Out

**Behavior:** For any household meal, each user can opt out individually. Opt-out means:
- The recipe's auto-scaling adjusts down (one fewer serving).
- The grocery list adjusts accordingly (if the user's dietary variation was the only reason for a specific ingredient, it's removed).
- The opted-out user's Plan page shows the slot as available for personal planning.

**This is consistent with Section 5.6 step 5 in the ADR** ("Each user opts in or out per meal") — we're implementing the opt-out UX.

---

## 5. Recipe Card Quick Actions

### 5.1 Surfaces

Every recipe card on every surface (homepage feed, recipe browse, search results, meal plan, menus) shows:
- **Bookmark button:** Toggles `is_bookmarked`. If bookmarking, optionally prompts for menu assignment (default: no menu). Shows filled bookmark icon if already bookmarked.
- **Like button:** Toggles `is_liked`. Shows filled heart if already liked. (Note: the existing heart icon on RecipeCard currently maps to `is_favorite` — this becomes the "like" icon.)
- **Add to plan button:** Opens a date/meal-type picker to add the recipe to a specific meal plan slot.
- **State indicators:** Bookmarked and liked states are visible at a glance. If the recipe is already on this week's meal plan, show a calendar badge.

### 5.2 Persistence Trigger

When a user taps bookmark, like, or add-to-plan on a non-persisted recipe (`is_persisted = false`):
1. Set `is_persisted = true` on the recipe.
2. Create the `UserRecipeRelation` row.
3. The recipe is now permanent.

This is invisible to the user — they just tapped a button. The persistence is a backend implementation detail.

### 5.3 Frontend Changes

**Files affected:**
- `frontend/src/components/recipe/RecipeCard.tsx` — Add bookmark button alongside existing heart. Update heart to represent "like" instead of "favorite." Add "add to plan" quick action.
- `frontend/src/components/recipe/ActionBar.tsx` — Update to use bookmark + like instead of single favorite toggle.
- `frontend/src/pages/RecipeDetail.tsx` — Update favorite toggle to like. Add bookmark button. Add "I cooked this" button (creates UserCookEvent). Rating UI gated by cook event existence.
- `frontend/src/api/` — New hooks: `useBookmarkRecipe`, `useLikeRecipe`, `useCookRecipe`, `useRateRecipe` (updated), `useHomeFeed`, `useMenus`, `useMenuRecipes`.
- `frontend/src/pages/Home.tsx` — Replace static section list with dynamic feed from `GET /feed/home`. Add "Make This Right Now" hero slideshow. Add "On Repeat" section. Add personalized + source rows.
- `frontend/src/pages/Recipes.tsx` — Update static carousel sections to include personalized rows. Source row "See all" navigates to filtered browse with browse cache expansion.
- `frontend/src/pages/Plan.tsx` — Replace Phase 3 stub with: weekly calendar view, household/personal toggle, auto-draft display, per-meal opt-out.

---

## 6. API Endpoints (New & Modified)

### 6.1 New Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/recipes/{id}/bookmark` | Toggle bookmark. Body: `{menu_id?: UUID}`. Triggers persistence if needed. |
| DELETE | `/recipes/{id}/bookmark` | Remove bookmark. |
| POST | `/recipes/{id}/like` | Toggle like. Triggers persistence if needed. |
| DELETE | `/recipes/{id}/like` | Remove like. |
| POST | `/recipes/{id}/cook` | Log a cook event. Body: `{notes?: string, meal_plan_entry_id?: UUID}`. |
| GET | `/recipes/{id}/cook-history` | Get user's cook events for this recipe. |
| POST | `/recipes/{id}/view` | Log a view event. Body: `{source?: string}`. Fire-and-forget (no user feedback). |
| GET | `/feed/home` | Personalized homepage feed for authenticated user. |
| GET | `/feed/browse` | Personalized recipe browse page feed (carousel sections). |
| GET | `/menus` | List user's menus (auto-generated + manual). |
| POST | `/menus` | Create a manual menu. Body: `{name, description?, filter_rules?}`. |
| PUT | `/menus/{id}` | Update menu (name, description, filter_rules). |
| DELETE | `/menus/{id}` | Delete menu. |
| GET | `/menus/{id}/recipes` | Get recipes in a menu (with pagination). |
| POST | `/menus/{id}/recipes` | Add recipe to menu. Body: `{recipe_id}`. |
| DELETE | `/menus/{id}/recipes/{recipe_id}` | Remove recipe from menu. |
| GET | `/plan/week` | Get weekly plan (household + personal for auth user). Query param: `week_start`. |
| POST | `/plan/draft/generate` | Trigger auto-draft generation for a specific week. |
| PUT | `/plan/entries/{id}/confirm` | Confirm a draft meal plan entry. |
| PUT | `/plan/entries/{id}/opt-out` | Opt out of a household meal. |

### 6.2 Modified Endpoints

| Method | Path | Change |
|---|---|---|
| POST | `/recipes/{id}/rate` | Now validates that user has at least one `UserCookEvent` for this recipe. Returns 403 with message "Rate after cooking" if no cook event exists. Accepts `rating_photos` and `rating_comment` in body. |
| GET | `/recipes/{id}/my-rating` | Renamed conceptually to "my relation" — returns bookmark, like, rating, and cook status. Response schema updated. |
| DELETE | `/recipes/{id}/my-rating` | Becomes "reset my relation" — clears rating/comment/photos but preserves bookmark/like state. Separate delete endpoints for bookmark and like. |
| GET | `/recipes/{id}/ratings` | Aggregate stats now include `bookmark_count` and `like_count` alongside existing `average_rating`, `rating_count`, `favorite_count` (deprecated, maps to `like_count`). |

### 6.3 Cleanup Job

**New scheduled task:** `prune_unpersisted_recipes`
- Runs daily (via the existing background task worker pattern).
- Deletes recipes where `is_persisted = false` AND `created_at < now() - BROWSE_CACHE_TTL_DAYS`.
- Also deletes orphaned `UserRecipeView` records for pruned recipes.
- Logs pruned count.

---

## 7. Phase Placement & Dependencies

### 7.1 Where This Fits in the Phase Plan

This work is a **new Phase 2.5** — inserted between the current Phase 2 (Recipe Ingestion) and Phase 3 (Smart Meal Planning). It's called **Phase 2.5: Recipe Engagement & Personalized Feed**.

**Rationale for new phase vs. extending Phase 3:**
- Phase 3 is already dense (Suggestion Engine + Auto-Scaling + Democratic Meal Planning + Daily Reconciliation).
- The bookmark/like/rating model and personalized feed are prerequisites for Phase 3A (Suggestion Engine uses the same behavioral signals).
- The auto-draft meal plan is a lighter precursor to Phase 3C that delivers immediate value.
- Users can start using FreshUp daily after Phase 2.5 without waiting for the full Phase 3 voting system.

### 7.2 Development Areas

| Code | Area | Dependencies |
|---|---|---|
| 2.5A | Data Model & Migration | 1B, 1E |
| 2.5B | Scraper Architecture Overhaul | 2C, 2.5A |
| 2.5C | Feed Engine (Backend) | 2.5A, 2.5B |
| 2.5D | Menu System (Backend) | 2.5A |
| 2.5E | Meal Plan Draft & Schedule (Backend) | 2.5A, 1F (grocery list for confirmed meals) |
| 2.5F | Frontend: Recipe Engagement UI | 2.5A, existing 1-FE components |
| 2.5G | Frontend: Home Feed & Browse | 2.5C, 2.5F |
| 2.5H | Frontend: Menus | 2.5D, 2.5F |
| 2.5I | Frontend: Plan Page | 2.5E, 2.5F |

### 7.3 Impact on Existing Phases

- **Phase 3A (Suggestion Engine):** Consumes `UserRecipeRelation`, `UserCookEvent`, and `UserRecipeView` as input signals. The feed engine queries built in 2.5C become reusable building blocks for 3A.
- **Phase 3C (Democratic Meal Planning):** The auto-draft feature (2.5E) is not a replacement. Phase 3C adds the full voting flow on top. The Plan page built in 2.5I provides the calendar UI that 3C extends with voting widgets.
- **Existing `UserRecipeRating` references:** All code touching this model must be updated during 2.5A. This is a cross-cutting migration — tests, routers, schemas, frontend hooks.

---

## 8. Sharkrite Directives

When generating issues from this plan, Sharkrite must observe:

1. **Dependency graph must be clean.** 2.5B depends on 2.5A completing (needs `is_persisted` column). 2.5C depends on 2.5A + 2.5B (needs new models + non-persisted recipes to exist). Frontend areas (2.5F–I) depend on their backend counterparts.

2. **The `UserRecipeRating` → `UserRecipeRelation` rename is the riskiest migration.** It touches models, routers, schemas, frontend hooks, and tests. This should be a single issue within 2.5A — not split across multiple issues — to avoid partial rename states that break the build.

3. **No phantom file references.** The existing files are:
   - Model: `src/db/models/user_recipe.py` (rename class, keep file or rename file)
   - Router: `src/routers/recipes.py` (rating endpoints live here)
   - Schemas: check `src/schemas/` for rating request/response schemas
   - Frontend: `frontend/src/api/` for hooks, `frontend/src/components/recipe/` for UI components

4. **Create-vs-extend awareness.** The `Menu` and `MenuRecipe` models are **new files**. The `UserCookEvent` and `UserRecipeView` models are **new files**. The `Recipe` model is **extended** (add `is_persisted`). The `UserRecipeRating` is **renamed and extended**. The scraper files are **modified** (not recreated).

5. **Test scope per issue.** Each issue should include its own tests. The migration issue (2.5A) must include tests that verify data migration correctness (existing `is_favorite=true` rows become `is_bookmarked=true`).

---

*This implementation plan was produced during the 2026-05-03 architecture session and reflects decisions made against the FreshUp ADR v1.0 and codebase at commit HEAD of main branch.*
