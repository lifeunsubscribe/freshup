# FreshUp: recipe acquisition frontend, design handoff

**From:** design session with Sarah, 2026-11-09 to 2026-11-10
**For:** Claude Code (Dace) and Sharkrite
**Checked against:** `lifeunsubscribe/freshup` `main` at `976d2d0` (2026-09-26). Anything pushed after that commit was not seen.
**Reconciled with:** `main` at `933e9f9` (2026-11-11) by Dace. Section 0 records what changed in between and which decisions Sarah has since made; the "Status" column in section 3 is current as of that commit.

This file records what was decided, what the mockups assume, and where the backend at that commit does not yet support them. It is not the ADR. `docs/FreshUp-ADR.md` stays the single source of truth; section 6 lists the ADR edits these decisions imply, and none of them have been applied.

## 0. Reconciliation with main, 2026-11-11

Written in Claude Code after reading the handoff against `main` at `933e9f9`. The design session saw `976d2d0`; these commits landed in between and change the ground the mockups stand on.

### What changed in the repo

- **Recipe import works again.** At `976d2d0` every HTTPS import failed (the SSRF guard connected by IP without SNI). Fixed in `a2fc39a`. `POST /scraper/import-url` is usable for the screen 1 link path as-is.
- **`GET /recipes/{id}` returns `ingredients`.** The preview and the Ingredients tab can read them; the frontend `RecipeResponse` type was corrected to match.
- **Import quality.** Titles no longer carry HelloFresh's tagline; "unit" and "(tsp)" are stripped from ingredient names; tags come from the page's category and cuisine; HelloFresh prep and cook times add up to the real total. Items with no amount are stored with quantity `0.001`, unit `""` and the warning `No amount given for: <name>`, so the preview's "gentle note" can print the `warnings` list from the import result verbatim.
- **HelloFresh discovery is clean.** The crawler reads the sitemaps the site declares in robots.txt and tells recipe pages (`/recipes/<slug>-<24 hex id>`) from collection pages. 15.5k recipe URLs, 218 collections.
- **Kitchen Sanctuary is confirmed saved-page only.** Its pages, sitemaps and WordPress API sit behind a Cloudflare bot challenge for non-browser clients; its RSS feed is open but carries titles and links only. The crawler now returns a clean error (HTTP 400) rather than a 500.

### Decisions Sarah has made since the session

| Topic | Decision | Effect on the mockups |
|---|---|---|
| Kitchen Sanctuary recipes | A recipe imported from a saved page is **browse cache like any other import** (`is_persisted = false`) until someone bookmarks it; unbookmarked imports are pruned by the cleanup job. (An earlier draft persisted them immediately; Sarah reversed that 2026-11-11.) | Screen 1 frames 4 and 9: "Save to library" is what keeps the recipe on both paths, and "Not this one" simply walks away. `is_persisted` still means "someone saved this". |
| Sources | HelloFresh and Kitchen Sanctuary only, for now. The API already restricts imports to those two domains. | The "any other recipe site" row in the supported-sources sheet (screen 1, frame 2) should be dropped or marked as not yet. |
| How HelloFresh fills the browse | **Collection-backed, with a catalog table.** A HelloFresh collection page serves 30 recipe cards (name, tagline, image, prep time, rating, URL) and lists its sub-collections, in one request and without touching a recipe page. Cards go in a catalog table separate from `Recipe`. Opening a card imports the full recipe on demand (one fetch) as an unpersisted recipe; bookmarking persists it. | This is the "opening a row brings in more" mechanism of screen 2. A pull is one collection-page fetch, cheap and bounded, so it is safe for any member (answers open question 1). Tail states map directly: *bringing in more* = fetching the collection page; *more arrived* = its cards; *caught up* = no sub-collections left; *could not bring in more* = fetch failed, which is also what source health reports. HelloFresh's own "load more" is a private API and `?page=` is disallowed by its robots.txt, so a row grows by walking sub-collections, not by paging. |
| Preview before saving | No parse-only mode. Both paths import as an unpersisted recipe and show that as the preview; "Save" bookmarks it. Confirmed 2026-11-11. | Answers open question 4 with one fetch per recipe and no new endpoint mode. |

### What this means for the gap table

Section 3 now carries a Status column. "Closed" means main already does it; "Reshaped" means the decision above replaces the row's original gap; "Open" is unchanged.

## 1. What is in this handoff

Suggested location in the repo:

```
docs/recipe-acquisition-frontend-handoff.md      (this file)
docs/mockups/recipe-acquisition/
  1-add-a-recipe.html      12 frames
  2-browse.html            10 frames
  3-recipe-detail.html     11 frames
  4-source-health.html      6 frames
```

Each mockup is one HTML file: 375px phone frames in a sideways-scrolling row, each with a numbered caption. Open it in a browser to see it.

### How to read the mockup source

- Tailwind loads from the CDN, with `theme.extend` copied from `frontend/tailwind.config.js`. Every class uses the real token names (`bg-cream`, `text-text-secondary`, `rounded-card-lg`, `border-warm-border`), so class strings copy straight into JSX.
- The markup is built by small JavaScript template functions in one `<script>` block, not written as flat HTML. Treat each function as a component sketch. The frames are the arrays at the bottom of each file (`ADD`, `SRC`, `RES`, `BROWSE`, `DETAIL`, `HEALTH`); each `phone(n, label, note, body)` call is one frame.
- Recipe photos are drawn placeholders (`food()`), because the preview could not load remote images. Use `Recipe.source_image` in the real build.
- All copy in the mockups is intended copy, including the olive period on titles and section headers.

### Mockup helpers and the components that already exist

Extend these; do not create parallel ones.

| Mockup helper | Existing component (`frontend/src/components/`) | What changes |
|---|---|---|
| `card()` / `rc()` | `recipe/RecipeCard.tsx`, `recipe/ConnectedRecipeCard.tsx` | "Saved" pill on the photo, "Not saved yet" and "New" context lines |
| `strip()` + `sec()` | `recipe/RecipeCarousel.tsx`, `ui/SectionHeader.tsx` | Subtitle that says why the row is there, optional "Pinned" marker |
| `sNav()` | `recipe/SectionNav.tsx` | Order follows the ranked rows |
| `gridHead()` + grid | `recipe/RecipeGrid.tsx`, `recipe/FilterChips.tsx` | Tail states: bringing in more, arrived, caught up, could not bring in more |
| `tabBar()` | `recipe/TabBar.tsx` | none |
| `ingTab`, pantry sheet | `recipe/IngredientsTab.tsx`, `recipe/PantryCheck.tsx` | Pantry check becomes a card that opens a review sheet |
| `stepList()` | `recipe/CookTab.tsx`, `recipe/RecipeStep.tsx` | Ingredient pills per step, "Start N min" buttons |
| `bar()` | `recipe/ActionBar.tsx` | "I cooked this" + "Add to plan"; bookmark and heart move to the top bar |
| `servings` | `recipe/ServingsControl.tsx` | 44px targets, labels above |
| `pill()`, `hpill()`, `badge()` | `ui/Pill.tsx` | none |
| `softAlert()`, failure cards | `ui/ErrorBanner.tsx` | Mocha (attention) variant, not terracotta |
| `nav()` | `layout/` | none |

New components with no existing counterpart: the add-a-recipe page, the supported-sources sheet, the sources hub and per-source page, the import preview card, the cook timer (top bar pills and setting sheet), the "Tonight's cook" sheet, the "How it turned out" list, the arrange-rows sheet, and the source-health rows.

## 2. Decisions, by screen

### Screen 1: add a recipe (`1-add-a-recipe.html`)

- One link box for every site. A HelloFresh link is not a separate path from a generic link.
- The saved-page path (paste the page or upload the file) sits directly under the link box. It exists for sites that refuse automated fetching, Kitchen Sanctuary first among them.
- "Which sources work?" opens a sheet listing HelloFresh (link works), Kitchen Sanctuary (saved page) and any other recipe site (try the link, saved page as backup). Each row leads to that source's page.
- A Kitchen Sanctuary link is caught before fetching and the user is pointed to the saved page. "Try the link anyway" remains available.
- A separate sources view is reached from "Browse by source": a hub, then a page per source.
  - On a source page, the add controls are collapsed behind an "Add a specific recipe" row that expands in place.
  - The page links out to the source's own website, under the title and inside the expanded section.
  - "Cooked most often" is pinned first on any source page where something has been cooked, and absent otherwise.
- After a link or a page is handed over, the states are: fetching, preview before saving, already in the library, could not import. The preview shows title, image, prep and cook time, servings, tags, and ingredients with quantity, unit and name. A quantity of `0.001` means no amount was given: show the name alone and list those names in one gentle note.
- Failed imports and duplicates are not urgent. Failures use mocha; duplicates use no alert color.

### Screen 2: browse (`2-browse.html`)

- There is no "Bring in more" button or sheet, and no coordinator step. Sources behave like channels.
- "Saved by the household." is pinned on top. Rows under it are ordered by what the household saves, likes and cooks, per tag and per source. Each row's subtitle says why it is there.
- Opening a row ("See all") is the request for more. What is already in the library shows at once, and more from that tag or source loads underneath. Arrivals are unsaved until someone bookmarks them, and carry a "New" marker.
- Tail states for an opened row: bringing in more, more arrived, caught up, could not bring in more (ties to source health).
- Kitchen Sanctuary cannot be pulled automatically, so its row grows only by hand. Its opened row says so and offers "Add a specific recipe".
- "Something different." always keeps a row at the bottom with recipes outside the pattern.
- "Why this order?" opens a sheet with plain counts per row.
- "Arrange rows" lets a user pin rows and drag them into order, and choose whether unpinned rows follow the pattern or a manual order. It is per user, not per household.
- Saved recipes show a filled olive bookmark and a "Saved" pill on the photo. Unsaved ones show an outline bookmark and "Not saved yet".
- Cold start: with no history, rows are labelled "A starting point".
- Frame 10 ("With a network") is exploratory only. See section 5.

### Screen 3: recipe detail (`3-recipe-detail.html`)

- Tabs: Ingredients (default), Cook & enjoy!, Nutrition.
- Bookmark and heart sit in the top bar. "I cooked this" and "Add to plan" are pinned to the bottom.
- Rating is possible only after cooking. Before the first cook, the page shows one muted line ("Ratings open up after the first cook.") and no prompt. Tapping "I cooked this" bumps the count and offers the rating once, in place of the action bar, with "Not now" to dismiss it.
- Just-cooked also offers "Add a photo or a variation", which opens a sheet for rating, photos and a free-text "What changed".
- Pantry check is a card that opens a review sheet. Needed items start ticked, in-stock items start unticked, and the user confirms before anything goes to the grocery list.
- "How it turned out." is a section under the tab content on every tab: photos, ratings and variations from the household. A fourth tab was rejected because four tabs do not fit at 375px.
- "Similar recipes." is a row under that, each card saying why it is similar, with "See all".
- On Cook & enjoy!, the top bar's right side holds timers in place of the heart and bookmark. A timer has an editable name and duration, several can run at once, and they stay visible while the steps scroll. A finished timer turns mocha until dismissed.
- Each step shows pills for the ingredients used in it. Steps whose text names a duration offer "Start N min".
- Nutrition shows the source's numbers when it gave any. When it gave none, show an estimate worked out from the ingredients, labelled "Estimated". Ingredients with no amount (oil, salt) are worked out at a light and a generous sample amount, which produces a range.
- Source attribution with a link to the original appears under the title and at the end of the steps.
- Grouping ingredients by category is deferred. The list is flat for now.

### Screen 4: source health (`4-source-health.html`)

- A daily check per source confirms it still imports the way it used to.
- Coordinators see one row per source in settings, in four states: healthy, failing, checking now, not checked. A failing row opens to show what the check found and what still works.
- Everyone sees a calm, mocha alert on the add screen when a source is failing ("HelloFresh imports have been failing since Tuesday. The saved page still works in the meantime."). Coordinators get one extra link through to the details.
- Pasting a link from a failing source gets the same pre-fetch nudge as Kitchen Sanctuary.
- Terracotta appears only on the coordinator's failing row.

## 3. What the mockups need that the repo does not have yet

Verified by reading the repo at `976d2d0`. "Not found" means a search turned up nothing, not proof of absence.

| Mockup feature | In the repo at `976d2d0` | Gap | Status (2026-11-11) |
|---|---|---|---|
| Paste a link | `POST /scraper/import-url` exists | No frontend code calls any `/scraper` route yet | Closed |
| Paste or upload a saved page | Not found in `src/routers/scraper.py` | Needs an endpoint that accepts page HTML (text or file) and runs the existing parser on it | Closed: `POST /scraper/import-html`, result is browse cache until bookmarked |
| Preview before saving | Not checked whether `import-url` can parse without persisting | Needs a parse-only mode, or the preview is shown after an unsaved (`is_persisted = false`) import | Recommendation in section 0: no parse-only mode |
| Opening a row brings in more, for any member | `import-batch`, `discover/{source}` and `discover-and-import/{source}` all call `require_coordinator` | **Permission change.** Either relax these for a bounded pull, or add a member-safe "bring in more for this row" endpoint | Closed: `GET /catalog/{source}/collections/{slug}` fetches on demand for any authenticated user (#525) (frontend: #545) |
| Row subtitle ("Saved 6 times and cooked 31 times here") | `FeedRowSchema` has `title`, `recipes`, `browse_url` | Needs a reason or counts field per row | Open |
| Saved versus not saved on cards | `RecipeCardSchema` has no `is_persisted` and no per-user bookmark state | Add both to the card schema | Closed for `CatalogCard` (#543); `RecipeCardSchema` still lacks bookmark state |
| Source badge and "view original" | `RecipeCardSchema` has `source_type` but not `source_url` | Add `source_url` where the link is shown | Closed on the detail page (#548); cards still lack `source_url` |
| Feed ranked by saves, likes and cooks | ADR section 0: feed scores on `UserRecipeRelation` and `times_cooked`; `UserCookEvent` and `UserRecipeView` are not wired in | Wire the cook and view signals into `feed_service` | Open |
| Arrange rows (pin, reorder) | `Menu.sort_order` exists for menus; nothing found for browse rows | Needs per-user row order and pin storage | Open |
| "Something different" row | `fallback_rows` exists on the home feed | Needs an always-present exploration row on browse | Open |
| Rating only after cooking | ADR section 0: open, issue #508 | Backend gate still to build | Open; issue #508 is written and unblocked |
| Five-point rating | `UserRecipeRelation.rating` is a float validated 0.0 to 5.0 | Fits as designed | Fits |
| Photo and "What changed" | `UserRecipeRelation.rating_photos` and `rating_comment` exist; `UserCookEvent.notes` exists (500 chars) | Decide which field holds the variation: per relation (one, overwritten) or per cook event (one each time). The mockup implies per cook event | Open question 2 |
| Submitting a rating | ADR section 0 warns `POST /recipes/{id}/rate` is a whole-relation upsert that clears fields it is not sent | The rating sheet must send the complete relation, or the endpoint needs a partial update | Open |
| "How it turned out" list | `GET /recipes/{id}/cook-history` and `GET /recipes/{id}/ratings` exist | Needs photos and comments per household member in one response | Open |
| Ingredient pills per step | `RecipeIngredient.step_index` exists | Scraped recipes may all have `step_index = null`; pills then need a "General" group or a matching pass | Open; imported recipes have `step_index = null` |
| "Start N min" on a step | Nothing found | Durations must be read from step text (deterministic pattern match) | Open |
| Cook timers | Nothing found | Frontend-only state is enough | Open |
| Similar recipes | Nothing found | Needs a similarity query on shared ingredients and tags | Open |
| Estimated nutrition | `Recipe.nutritional_info` exists | Needs an ingredient-to-nutrient lookup, an `estimated` marker, and ranges | Open question 5 |
| Source health check, rows and alert | Nothing found | Needs a daily job, stored status per source, and a status endpoint readable by members | Backend closed (#526, #527); rows #544; alert #547 |
| Pantry check sheet | `recipe/PantryCheck.tsx` exists | Needs per-ingredient in-stock results, not only a summary | Open |

Per the project's LLM boundary: similarity, ranking, nutrition arithmetic, duration extraction and the health check are deterministic code. The one place an LLM may fit is mapping free-text ingredient names to food-database entries for the nutrition estimate.

## 4. Assumptions in the mockups worth knowing

- "In Sarah's favs" is derived from `is_liked`. "Saved by the household" is derived from `is_persisted`. Per the ADR, a bookmark is private and a like is public, so check that "Saved by the household" should not be built from bookmarks.
- Counts shown on cards ("Cooked 12x") use `Recipe.times_cooked`, which is a global count across users.
- HelloFresh collection names, friend names, nutrition figures and recipe names in the mockups are placeholder content.
- The layouts were checked against a local Tailwind build using the project config. The published mockups load Tailwind from the CDN.

## 5. Decided in principle, not designed. Do not build from this section.

These came up at the end of the session. They change the product's shape and belong in the ADR before any issue is written. ADR section 10 currently lists the social platform as out of scope, and section 11 lists multi-household support as an open question.

- **Friends are separate from households.** Sharing a household does not require friendship, and friendship does not imply a household.
- **Friendship is the privacy barrier** for seeing another person's likes, ratings, photos and variations. Bookmarks stay private.
- **Public profiles.** A user may set their profile public, which shows that same information to anyone with the profile link.
- **Meal plans are individual first.** Every user can make their own plan. A joint plan opens when a user coordinates a meal with one or more other people.
- **Household membership does not oblige anyone to join a house plan.** The household holds everyone's patterns and preferences and uses them for suggestions and shared views. The resulting plan is opt-in.
- **Two ways into a joint plan:** opting in, or receiving a request on a recipe to coordinate with one or more people. (`MealPlanEntry.user_opt_ins` already exists and may be the basis.)
- **The coordinator owns the house plan** and may post it without exposing other members or their individual contributions.
- **Feed rows from a network:** "Popular with friends" as a featured row, plus rows that cross a liked tag with an unfamiliar source, or surface a category popular with friends.
- **Hosting.** Friends would most likely reach Sarah's server over Tailscale. Hosting it properly is possible later, keeping a privacy-forward stance. Either way this is multi-household on one server, which is ADR open question 8.

## 6. ADR edits these decisions imply (not applied)

| ADR section | Edit |
|---|---|
| 0 | Add recipe-acquisition frontend as a tracked area; note the mockups |
| 5.10 / Design System | Pinned rows, row subtitles, "Saved" pill, mocha for failed imports, timers in the Cook tab top bar |
| 5.11 | Photo and variation on a cook; "How it turned out"; rating offered once after cooking |
| 5.12 / 6.7 | Opening a row triggers a bounded pull; arrivals stay unpersisted until bookmarked |
| 5.14 | Browse ranking by saves, likes and cooks per tag and source; exploration row; per-user arrange |
| 6.2 / 6.3 / 6.4 | One link box for all sites; saved-page import path; Kitchen Sanctuary is saved-page only |
| 6 (new) | Source health: daily check, statuses, member-visible alert |
| 8 | Phase placement for all of the above |
| 10 / 11 | Move the social and plan model in section 5 of this file from "not designed" to an open design item |

## 7. Open questions for Sarah

1. Should members be able to trigger a bounded pull by opening a row, or should the coordinator keep a per-source "bring in automatically" switch?
   *Answered 2026-11-10: members may. The pull is one collection-page fetch (30 cards), not a batch of recipe imports, so it is cheap and bounded. See section 0.*
2. Where does a cook's variation live: on the cook event, or on the user's relation to the recipe?
3. Is "Saved by the household" built from `is_persisted`, from bookmarks, or from likes?
   *Narrowed 2026-11-11: `is_persisted` again means "someone bookmarked this" on every path, so it is a usable household-level signal; bookmarks or likes remain the per-user choice.*
4. Does the preview need a true parse-without-saving mode, or is an unpersisted import acceptable as the preview?
   *Answered 2026-11-11: the unpersisted import is the preview on both paths.*
5. Which food database backs the nutrition estimate, and what are the two sample amounts for oil and salt?

## 8. Suggested order of work

1. Screen 1 link path end to end: add page, fetching, preview, duplicate, failure, wired to `POST /scraper/import-url`.
2. Saved-page endpoint, then the saved-page UI and the Kitchen Sanctuary pre-fetch catch.
3. Recipe detail items whose backend already exists: "I cooked this", add to plan, top-bar bookmark and heart, step pills, timers, pantry review sheet.
4. Rating gate (issue #508), then the just-cooked strip and the photo and variation sheet.
5. Card and feed schema additions, then the browse rows with subtitles and the saved-versus-unsaved treatment.
6. Member-safe "bring in more" and the opened-row tail states.
7. Source health job, rows and alert.
8. Arrange rows, similar recipes, estimated nutrition.
