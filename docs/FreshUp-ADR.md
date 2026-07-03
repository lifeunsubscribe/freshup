# FreshUp — Architecture Decision Record

**Project:** FreshUp — Privacy-First Kitchen Management System  
**Author:** Sarah  
**Date:** 2026-03-13  
**Status:** Approved — Ready for Phase Implementation  
**ADR Version:** 1.1 (amended 2026-05-03 — Recipe Engagement & Personalized Feed)

---

## 1. Context & Problem Statement

FreshUp replaces the convenience of a meal kit subscription service (specifically HelloFresh) with a self-hosted, privacy-first kitchen management system that operates at the same standard — browse recipes, pick your week, auto-generate grocery lists — while eliminating the premium cost model of pre-portioned ingredient delivery.

The system serves a multi-person household (3+ users) with mixed dietary requirements (including at least one vegan) and aims to solve the following problems:

- **Meal planning friction:** Deciding what to cook, coordinating preferences across housemates, and avoiding repetition requires significant mental overhead.
- **Inventory blindness:** No clear picture of what's in the kitchen leads to waste (forgotten perishables), redundant purchases, and missed meal opportunities.
- **Recipe fragmentation:** Recipes exist across physical HelloFresh card binders, bookmarked websites, screenshots, handwritten notes, and memory — with no unified searchable system.
- **Grocery list coordination:** Multiple people shop at multiple stores with no shared, real-time list. Items get duplicated or missed.
- **Privacy concerns:** Commercial meal planning apps collect and monetize user data. Voice assistants (Alexa, Google) record conversations and share data with third parties. FreshUp keeps all data under the user's control.

### 1.1 Design Philosophy

FreshUp should feel like having a knowledgeable sous chef — one who knows what's in your kitchen, remembers what everyone likes, warns you when food is going bad, and can creatively suggest meals from what's available. The system should reduce cognitive load, not add it.

**Core UX principle:** Every feature must pass the "would we actually use this daily?" test. If it adds friction, it doesn't ship.

---

## 2. Decision Drivers

| Driver | Weight | Notes |
|---|---|---|
| Privacy | High | All sensitive data (especially voice) stays local. No third-party data sharing. |
| Zero subscription cost | High | No recurring fees for AI, hosting, or services. One-time hardware costs only. |
| Multi-user household support | High | 3+ users with different dietary needs, preferences, and cooking roles. |
| Daily usability | Critical | The system must be convenient enough that the household actually adopts it. |
| Extensibility | Medium | Design for future mobile app, cloud deployment, and voice interface without over-engineering now. |
| Portfolio value | Medium | Architecture should demonstrate professional-grade design decisions. |
| Reusable receipt parsing | Medium | Receipt OCR module should be designed for potential reuse in a future price-tracking product. |

---

## 3. Architecture Overview

### 3.1 System Topology

```
┌─────────────────────────────────────────────────────┐
│                    HOME NETWORK                      │
│                                                      │
│  ┌──────────┐    HTTP/WiFi    ┌──────────────────┐  │
│  │  iPad     │◄──────────────►│  Dell Laptop     │  │
│  │  (Safari) │                │  (Ubuntu Server)  │  │
│  │  Kitchen  │                │  ┌────────────┐   │  │
│  │  Terminal │                │  │  FastAPI    │   │  │
│  └──────────┘                │  │  Backend    │   │  │
│                               │  └─────┬──────┘   │  │
│  ┌──────────┐    HTTP/WiFi   │  ┌─────┴──────┐   │  │
│  │  Phone   │◄──────────────►│  │  SQLite    │   │  │
│  │  Browser │                │  │  (SQLAlchemy)│  │  │
│  │  (Per    │                │  └────────────┘   │  │
│  │  User)   │                │  ┌────────────┐   │  │
│  └──────────┘                │  │  Ollama     │   │  │
│                               │  │  (Local LLM)│  │  │
│  ┌──────────┐  Future Phase  │  └────────────┘   │  │
│  │  Raspi   │◄──────────────►│  ┌────────────┐   │  │
│  │  (Voice) │                │  │  MinIO      │   │  │
│  │  Whisper │                │  │  (S3-compat)│   │  │
│  │  + Piper │                │  └────────────┘   │  │
│  └──────────┘                └──────────────────────┘│
│                                                      │
└─────────────────────────────────────────────────────┘
```

**Primary access pattern:** Each household member accesses FreshUp through their phone's web browser. The iPad serves as a shared kitchen terminal (wall-mounted or counter-mounted). All clients connect to the Dell server over the home WiFi network.

**Server access:** The Dell laptop runs headless (lid closed, lid-close action set to "do nothing" in BIOS/logind.conf), connected via ethernet to the home router for reliability. Administered via SSH from any device on the network.

### 3.2 Key Architecture Decisions

#### ADR-001: Local-First, Cloud-Ready

**Decision:** Develop and run locally on the Dell home server. Design abstractions that allow migration to AWS without code changes.

**Rationale:** Local development provides zero cost, instant iteration, maximum privacy, and no dependency on internet connectivity. AWS migration path is preserved through:
- SQLAlchemy ORM (swap SQLite → RDS Postgres via connection string)
- MinIO for local S3-compatible object storage (swap to real S3 via endpoint config)
- Docker containerization from day one (deploy to ECS/Fargate with docker-compose → ECS task definition)
- Environment-based configuration (`.env` file switches between local and cloud)

**Tradeoff:** The Dell must be running for the app to work. Acceptable for a household tool; addressed in Phase 6 with cloud deployment.

#### ADR-002: React Frontend

**Decision:** Use React (with hooks, no Redux) and Tailwind CSS for the web UI. Served as a static build from the FastAPI backend.

**Rationale:** FreshUp has complex interconnected state — meal plan calendars with per-user opt-in, real-time grocery list updates, dietary filter toggling, voting interfaces. React's declarative component model handles state propagation cleanly. Component reusability (e.g., `RecipeCard` used on browse, meal plan, favorites, and suggestion screens) avoids HTML duplication. Tailwind provides rapid styling without custom CSS management. React Native provides a future path to native mobile apps with shared component logic.

**Rejected alternative:** Vanilla HTML/CSS/JS — sufficient for CRUD but becomes unmanageable with multi-user interactive state and would require a full rewrite at Phase 3.

#### ADR-003: LLM for Interpretation, Deterministic Code for Execution

**Decision:** Ollama (running locally on the Dell) handles natural language interpretation tasks. All state management, math, and business logic is handled by deterministic Python code.

**Rationale:** LLMs are good at understanding messy input (OCR text, natural language queries, recipe photos) and generating creative suggestions (substitutions, meal ideas). They are bad at math, state management, and consistency. The boundary is:

**LLM handles:**
- Receipt text parsing (messy OCR output → structured data)
- Recipe parsing from photos (handwritten cards, printed pages)
- Natural language queries ("what should I eat tonight?")
- Creative substitution suggestions
- Voice command interpretation (future phase)

**Deterministic code handles:**
- Inventory CRUD operations
- Grocery list generation and management
- Meal plan scheduling and conflict resolution
- Recipe scaling math
- Expiration date calculations
- Freshness priority scoring
- Consumption pattern analysis
- Dietary compatibility filtering

**Hardware requirement:** The Dell has 32GB RAM, which comfortably runs a 7B parameter model (e.g., Llama 3 8B quantized) via Ollama with room for the web server and database.

#### ADR-004: Privacy Boundary — Voice Local, Data Cloud-Eligible

**Decision:** Voice processing (speech-to-text, text-to-speech) must always be processed locally and never transmitted to external servers. Recipe, inventory, and meal plan data may be hosted in the cloud with customer-managed encryption keys (CMK) if/when the system migrates to AWS.

**Rationale:** The primary privacy concern is ambient surveillance — voice conversations being recorded, stored, and accessible to third parties. Grocery and recipe data, while personal, does not carry the same surveillance risk. A CMK-encrypted cloud database (e.g., AWS RDS with KMS) where the user controls the decryption key provides adequate privacy for non-voice data while enabling mobile access outside the home network.

#### ADR-005: SQLite for MVP, Postgres for Scale

**Decision:** Use SQLite as the database engine for all local development phases. Migrate to PostgreSQL (via RDS) only when cloud deployment or concurrent multi-user write performance demands it.

**Rationale:** SQLite is zero-config, file-based, and more than capable for a single-household application. SQLAlchemy ORM abstracts the engine, so migration to Postgres requires only a connection string change. Premature Postgres adoption adds unnecessary infrastructure complexity (running a database server, managing connections, backups) with no benefit at household scale.

#### ADR-006: Docker from Day One

**Decision:** Containerize the application using Docker and docker-compose from the first phase.

**Rationale:** Ensures environment parity between development (Mac) and production (Dell). Simplifies Dell server setup (install Docker, pull image, run). Provides direct path to AWS ECS/Fargate deployment in Phase 6. Makes the entire application portable and reproducible.

---

## 4. Data Model

### 4.1 Entity Definitions

#### User
| Field | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| name | String | Display name |
| role | Enum | `coordinator` / `member` — coordinator has meal plan approval authority |
| dietary_profile | Enum[] | Multi-select: `omnivore`, `vegetarian`, `vegan`, `pescatarian`, `keto`, `low_carb`, `low_sugar` |
| allergies | String[] | Freeform: `lactose`, `gluten`, `tree nuts`, etc. |
| disliked_ingredients | FK[] | Links to Ingredient entities |
| favorite_ingredients | FK[] | Ranked list, used to boost suggestion priority |
| favorite_recipes | FK[] | Links to Recipe entities via UserRecipeRelation (bookmarked or liked) |
| preferred_substitutions | FK[] | Links to SubstitutionPreference entities |

#### InventoryItem
| Field | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| name | String | Display name |
| quantity | Float | Current amount |
| unit | Enum | `oz`, `lb`, `g`, `kg`, `ml`, `l`, `count`, `pack`, etc. |
| category | Enum | `produce`, `protein`, `dairy`, `grain`, `pantry_staple`, `frozen`, `snack`, `condiment`, `beverage`, etc. |
| vegan_friendly | Boolean | Dietary filter flag |
| storage_location | Enum | `pantry`, `fridge`, `freezer` |
| date_added | DateTime | When entered into inventory |
| expiration_date | DateTime? | Optional — nullable for shelf-stable items |
| frozen_date | DateTime? | When item was frozen (for freshness tracking) |
| is_staple | Boolean | If true, triggers restock alert at minimum_threshold |
| minimum_threshold | Float? | Restock trigger point (staples only) |
| shareability | Enum | `shared` / `reserved` / `personal` |
| reserved_for | FK? | Link to MealPlanEntry if reserved for a specific meal |
| reserved_note | String? | "For Saturday's cheesecake — don't touch" |
| added_by | FK | Link to User who added/purchased |
| price | Decimal? | Optional — for future price tracking integration |
| brand | String? | Optional |
| preferred_store | FK? | Link to Store — where this item is typically purchased |
| available_at_stores | FK[] | Links to Store entities where this item can be found |

#### Store
| Field | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| name | String | `Costco`, `Save-A-Lot`, `King Soopers`, etc. |
| has_digital_receipts | Boolean | Whether digital receipt parsing is available |
| parsing_profile | JSON? | Store-specific OCR hints and formatting rules |

#### Recipe
| Field | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| name | String | Display name |
| source_type | Enum | `hellofresh_card`, `hellofresh_web`, `kitchen_sanctuary`, `url_import`, `manual`, `photo_upload`, `ad_hoc` |
| source_url | String? | Original URL if web-sourced |
| source_image | String? | Path to uploaded photo if card/handwritten |
| ingredients | FK[] | Links to RecipeIngredient join table (ingredient + quantity + unit + variation_group) |
| variation_groups | JSON? | Defines dietary forks — e.g., `{"protein": {"omnivore": "ground beef", "vegan": "spiced tofu"}, "cheese": {"omnivore": "cheddar", "vegan": "vegan shredded cheese"}}` |
| steps | Text[] | Ordered preparation steps |
| prep_time_minutes | Int? | |
| cook_time_minutes | Int? | |
| base_servings | Int | Recipe's default serving count |
| tags | String[] | Cuisine, method, difficulty, etc. |
| nutritional_info | JSON? | Calories, protein, carbs, fat per serving (if available) |
| user_ratings | FK[] | Per-user bookmark/like/rating status (via UserRecipeRelation) |
| times_cooked | Int | Global cook count — drives familiar-first ranking |
| is_persisted | Boolean | Default true. Scraped/browsed recipes enter as false; set to true when any user bookmarks, likes, or adds to meal plan. Non-persisted recipes are pruned after configurable TTL (default 7 days). |
| created_by | FK? | User who created ad-hoc recipes |
| notes | Text? | User notes, tips, modifications |

#### RecipeIngredient (Join Table)
| Field | Type | Notes |
|---|---|---|
| recipe_id | FK | |
| ingredient_name | String | Canonical ingredient name |
| quantity | Float | Amount for base_servings |
| unit | String | |
| variation_group | String? | If set, this ingredient belongs to a dietary fork |
| variation_diet | Enum? | Which dietary profile this variation serves |
| is_optional | Boolean | Garnishes, toppings, etc. |

#### PreparedFood
| Field | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| name | String | Display name (e.g., "Sweet Potato Chickpea Curry", "Veggie Stock Blocks") |
| source_recipe | FK? | Link to Recipe if applicable |
| type | Enum | `complete_meal` / `batch_portion` / `component_ingredient` |
| servings_remaining | Float | Decremented as consumed |
| storage_location | Enum | `fridge` / `freezer` |
| date_prepared | DateTime | |
| estimated_expiration | DateTime? | |
| shareability | Enum | `shared` / `reserved` / `personal` |
| prepared_by | FK | Link to User |
| notes | String? | |

*Note: `component_ingredient` type items (e.g., veggie stock blocks, caramelized onion pucks) are treated as available inventory by the recipe suggestion engine. When a recipe calls for vegetable stock and stock blocks exist, the system does not add stock to the grocery list.*

*Note: PreparedFood items with `shareability=shared` can be consumed by any authenticated household member. Items with `shareability=personal` or `shareability=reserved` can only be consumed by the `prepared_by` user.*

#### MealPlanEntry
| Field | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| date | Date | |
| meal_type | Enum | `breakfast` / `lunch` / `dinner` / `snack` |
| recipe | FK? | Link to Recipe |
| prepared_food | FK? | Link to PreparedFood (for leftover meals) |
| planned_servings | Int | Total servings to prepare |
| make_extra | Boolean | If true, planned_servings exceeds opt-in count for intentional leftovers |
| extra_servings_purpose | String? | "Lunch leftovers for Tuesday" |
| user_opt_ins | FK[] | Users participating in this meal |
| user_variations | JSON | Per-user variation assignments — e.g., `{"user_id_1": "vegan", "user_id_2": "omnivore"}` |
| status | Enum | `draft` / `voting` / `approved` / `shopping` / `ready` / `cooked` / `skipped` / `pushed` |
| leftovers_generated | FK? | Link to PreparedFood created after cooking |
| notes | String? | User notes for this specific instance |

#### GroceryListItem
| Field | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| item_name | String | |
| quantity | Float | |
| unit | String | |
| source | Enum | `meal_plan_auto` / `staple_threshold` / `manual` / `consumption_pattern` |
| linked_recipe | FK? | Why this item is needed |
| linked_meal_plan_entry | FK? | Specific meal this supports |
| added_by | FK | User who added (or `system` for auto-generated) |
| target_store | FK? | Link to Store — based on ingredient-store mapping |
| purchased | Boolean | Checked off at store |
| purchased_by | FK? | Who bought it |
| purchased_date | DateTime? | |

#### SubstitutionPreference
| Field | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| user | FK | Link to User |
| original_ingredient | String | Ingredient being replaced |
| replacements | JSON | Ranked list: `[{"ingredient": "asparagus", "rank": 1}, {"ingredient": "carrots", "rank": 2}]` |
| context | Enum? | `side_dish` / `in_recipe` / `protein` / `sauce` / `any` |

*Substitution logic: When suggesting replacements, the system checks inventory availability first and promotes in-stock alternatives to the top of the ranked list regardless of stored rank order.*

#### ConsumptionPattern
| Field | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| item_name | String | Canonical name of the tracked item |
| purchase_dates | DateTime[] | History of purchases |
| depletion_dates | DateTime[] | When marked as finished (or inferred from repurchase) |
| avg_interval_days | Float? | Calculated after 3+ data points |
| consistency_score | Float? | Standard deviation of intervals — low = predictable |
| notification_threshold | Float | Percentage of avg_interval at which to alert (default 0.8) |
| active | Boolean | Only generates suggestions if true — auto-disabled for inconsistent patterns |

*Pattern learning triggers: Suggestions are only generated for items with 3+ purchase cycles AND a consistency score below a defined threshold. Items purchased irregularly (high variance) are excluded from proactive suggestions. All suggestions are advisory — the system never auto-adds to the grocery list without user confirmation.*

#### UserRecipeRelation (replaces UserRecipeRating as of v1.1)
| Field | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| user_id | FK | Link to User |
| recipe_id | FK | Link to Recipe |
| is_bookmarked | Boolean | "Save for later" — private utility, personal queue. |
| is_liked | Boolean | "I endorse this" — public-facing curation, visible on user profile. |
| rating | Float? | 0.0–5.0. Nullable. **Gated:** API rejects rating submissions unless the user has at least one `UserCookEvent` for this recipe. DB allows null freely for migration flexibility. |
| rating_photos | JSON? | Array of MinIO object keys for photos attached to the rating. Only accepted post-cook. |
| rating_comment | String(2000)? | Post-cook commentary, tips, modifications. |
| menu_id | FK? | Default menu assignment on bookmark. Nullable. |
| created_at | DateTime | |
| updated_at | DateTime | |

*Unique constraint: `(user_id, recipe_id)`. Each user has one relation row per recipe. Bookmarks and likes are independent — a user can bookmark without liking and vice versa. Ratings require a cook event.*

#### Menu
| Field | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| user_id | FK | Owner |
| name | String(255) | Display name. User-editable. Auto-generated menus get descriptive defaults. |
| description | String(500)? | Optional |
| filter_rules | JSON? | For auto-generated menus: rules that populate the menu. Schema: `{"match": "all"/"any", "rules": [{"field": "tags", "op": "contains", "value": "indian"}]}`. Null for manual menus. User-editable. |
| is_auto_generated | Boolean | True if system-created. Can still be edited. |
| cover_image | String? | MinIO key. Defaults to first recipe's image. |
| sort_order | Integer | For ordering in user's menu list and homepage rotation |
| created_at | DateTime | |
| updated_at | DateTime | |

*Filter rule fields: `tags` (contains/not_contains), `source_type` (eq/in), `cook_time_minutes` (<=/>=/eq), `nutritional_info.calories` (<=/>=/eq). `match: "all"` = AND, `match: "any"` = OR. User can edit rules to narrow or expand auto-generated menus (e.g., "Indian cuisine" → "Indian sides under 500 calories").*

#### MenuRecipe (Join Table)
| Field | Type | Notes |
|---|---|---|
| menu_id | FK | |
| recipe_id | FK | |
| sort_order | Integer | Position within menu |
| manually_added | Boolean | Immune to filter rule changes |
| manually_removed | Boolean | Suppresses re-addition by filter rules |
| added_at | DateTime | |

*Composite PK: `(menu_id, recipe_id)`.*

#### UserCookEvent
| Field | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| user_id | FK | Link to User |
| recipe_id | FK | Link to Recipe |
| cooked_at | DateTime | |
| meal_plan_entry_id | FK? | Link to MealPlanEntry if applicable |
| notes | String(500)? | Optional cook notes |

*Created when: MealPlanEntry transitions to `cooked` status, or via manual `POST /recipes/{id}/cook` endpoint. Gates rating submissions — users can only rate recipes they've cooked.*

#### UserRecipeView
| Field | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| user_id | FK | Link to User |
| recipe_id | FK | Link to Recipe |
| viewed_at | DateTime | |
| source | String(50)? | Where the view happened: `browse`, `detail`, `search`, `feed`, `menu` |

*No unique constraint — multiple views per user per recipe are recorded. Used as a feed signal: high views relative to zero cook events indicates interest without commitment.*

#### WeeklyMealPlanVote
| Field | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| week_start | Date | Monday of the plan week |
| status | Enum | `candidate_generation` / `ranking` / `draft_review` / `approved` / `active` |
| candidate_recipes | FK[] | System-generated list of recipe candidates |
| user_rankings | JSON | Per-user ranked selections with notes: `{"user_id": {"recipe_id": {"rank": 1, "notes": "make extra!", "hard_no": false}}}` |
| draft_plan | FK[] | System-generated draft meal plan from aggregate rankings |
| approved_by | FK? | Coordinator who approved the final plan |
| approved_date | DateTime? | |

### 4.2 Entity Relationship Summary

```
User ──┬── owns ──► SubstitutionPreference
       ├── relates to ──► Recipe (via UserRecipeRelation: bookmark, like, rate)
       ├── cooks ──► Recipe (via UserCookEvent)
       ├── views ──► Recipe (via UserRecipeView)
       ├── owns ──► Menu
       ├── opts into ──► MealPlanEntry
       └── adds ──► GroceryListItem

Recipe ──┬── contains ──► RecipeIngredient
         ├── produces ──► PreparedFood (after cooking)
         ├── referenced by ──► MealPlanEntry
         └── belongs to ──► Menu (via MenuRecipe)

Menu ──── contains ──► Recipe (via MenuRecipe, with manual add/remove overrides)

InventoryItem ──┬── purchased at ──► Store
                └── reserved for ──► MealPlanEntry

MealPlanEntry ──┬── generates ──► GroceryListItem (auto, only when confirmed)
                ├── produces ──► PreparedFood (leftovers)
                └── belongs to ──► WeeklyMealPlanVote

ConsumptionPattern ──► suggests ──► GroceryListItem

PreparedFood ──► feeds back into ──► MealPlanEntry (as leftover meal)
PreparedFood (component) ──► acts as ──► InventoryItem (for recipe matching)
```

---

## 5. Key Feature Specifications

### 5.1 Home Screen Quick Actions

The home screen surfaces the most common daily interactions as single-tap shortcuts to minimize friction:

- **"I shopped"** → Receipt upload (camera/file) or search-and-select for manual item entry. Triggers inventory update pipeline.
- **"I froze / thawed items"** → Quick selector from current inventory to update storage location and set freeze/thaw dates.
- **"I ate snacks"** → Checklist of available snack-type items and shared leftovers. Decrements inventory and logs consumption per user.
- **"What's around?"** → Snack suggestion view: available standalone ingredients (fruit, cheese sticks, crackers), prepared snacks, and open shared leftovers.
- **"What's for dinner?"** → Today's meal plan with status, or suggestion engine if nothing is planned.

### 5.2 Suggestion Engine Priority Queue

When generating meal suggestions, the system evaluates candidates in this priority order:

1. **Expiring leftovers / prepared foods** — fridge items approaching expiration get surfaced first.
2. **Fresh ingredients at risk** — inventory items nearing expiration that could anchor a meal.
3. **Planned meals on the schedule** — already-approved meal plan entries.
4. **Familiar recipes (previously cooked)** — weighted by cook frequency and user ratings. Familiar-first is the default.
5. **New recipe suggestions** — from the recipe database, filtered by dietary compatibility and inventory availability.
6. **Escape hatch: "Show me something totally new"** — bypasses familiarity weighting, still filtered by inventory and dietary needs.

### 5.3 Recipe Auto-Scaling with Leftovers Toggle

- When a meal plan entry is created, the system counts opted-in users and auto-scales the recipe to match.
- A "make extra" toggle allows intentional over-production for meal prep / leftovers.
- When make-extra is enabled, the user specifies extra serving count and purpose ("Tuesday lunch leftovers").
- After cooking, the system prompts to log leftovers as a PreparedFood entry with appropriate servings, storage location, and expiration.

### 5.4 Split Recipe / Dietary Variation Support

For meals where the household shares a base recipe but individuals need dietary modifications:

- Recipes can define **variation groups** — ingredient slots that fork based on dietary profile.
- Example: Taco night — tortillas and pico are shared base. Protein slot forks: ground beef (omnivore) vs. spiced tofu (vegan). Cheese slot forks: cheddar vs. vegan shredded cheese.
- The grocery list generator produces ingredients for the shared base PLUS all required variations based on who opted in.
- Users see their personalized version of the recipe with their variation highlighted.

### 5.5 Ad-Hoc Recipe Creation from Inventory

Users can create recipes directly from what they just cooked:

- Select ingredients from current inventory (search and select UI).
- Optionally add external ingredients via search-and-insert (e.g., Kraft Three Cheese Mac).
- Add steps, notes, and a name.
- Save as a new recipe entry with `source_type: ad_hoc`.
- Inventory is decremented accordingly.
- Recipe is immediately available for favoriting and future suggestion.

### 5.6 Democratic Meal Planning Flow

**Weekly cycle:**

1. **Candidate generation** — System generates a broad list of recipe candidates based on: current inventory and freshness priorities, household dietary compatibility, familiar-first ranking (previously cooked recipes weighted higher), and seasonal/available ingredients. The candidate list is the same for all users.
2. **Individual ranking** — Each user browses the candidate list and builds their personal ranked selection. During ranking, users can: modify recipes (suggest substitutions or variations), add notes for other household members to see, flag hard vetoes ("absolutely not this week"), and add recipes not in the candidate list (from favorites or the full database).
3. **Draft generation** — After a configurable deadline, the system generates a draft weekly plan by aggregating all user rankings, weighting by dietary constraints and inventory optimization.
4. **Coordinator review** — The coordinator (primary cook) reviews the draft, seeing everyone's votes and notes as context. The coordinator can approve as-is, adjust (swap days, substitute recipes, override votes), or send back for another round.
5. **Publication** — The approved plan publishes to all users. Each user opts in or out per meal.
6. **Opt-out self-service** — Users who opt out of a meal can browse available shared inventory and build their own meal plan for that slot.

### 5.7 Daily Reconciliation Check-In

Once per day (triggered on login or at a configured time), the system prompts each user:

- **Meal confirmation:** "Did you eat [planned meal] last night?" → Yes (decrements inventory, logs consumption) / No (meal pushed or skipped).
- **Snack consumption:** "Check off anything you ate today" → list of available snack items and open leftovers.
- **Expiration alerts:** "These items are expiring soon: [list]. Want to plan a meal around them?"
- **Grocery suggestions:** "Based on your patterns, you might need bananas soon. Add to list?"

This passive tracking enables approximate per-user calorie and macro tracking over time (noted future capability — not designed in detail for MVP).

### 5.8 Consumption Pattern Learning

- The system tracks purchase and depletion events per item.
- After 3+ complete consumption cycles, it calculates an average interval and consistency score.
- **Only items with high frequency AND high consistency** generate proactive restock suggestions (e.g., buys bananas at least twice a month with regular cadence).
- Items with irregular purchase patterns (e.g., specialty hot sauce bought twice in 8 months) are excluded from proactive suggestions.
- All suggestions are advisory — no auto-additions to grocery lists without explicit user confirmation.
- Notifications surface at ~80% of the average consumption interval.

### 5.9 Store-Ingredient Mapping

- Each InventoryItem can be associated with one or more Stores where it's available, plus a preferred store.
- The grocery list generator groups items by target store, producing separate per-store shopping lists.
- Store associations are learned over time from receipt parsing (if an item appears on a Costco receipt, it's marked as available at Costco).
- Manual override is always available.

### 5.10 Frontend Design System & UI Architecture

The frontend design is documented in a companion file: `docs/FreshUp-Design-System.md`. Key architectural decisions are summarized here for ADR completeness.

**Design philosophy:** Inspired by Mealime's warm, un-intimidating aesthetic. The UI uses earth tones (olive green, café mocha, warm cream) rather than typical SaaS blues. The palette, typography, spacing, component specs, and Tailwind theme configuration are fully defined in the design system doc.

**Screen architecture:** Five bottom-nav tabs (Home, Plan, Recipes, Pantry, List) map directly to API router domains. The Recipes tab uses a Spotify-style carousel browse as the default view, with "See all" transitioning to a filtered grid. Recipe detail defaults to the Ingredients tab (budget assessment before cooking commitment), with a Cook & enjoy! tab showing inline ingredients per step.

**Inline ingredients per step:** The Cook tab displays each recipe step with its relevant ingredients shown as pills directly below the instruction text, eliminating the scroll-back-and-forth problem common on recipe websites. This requires a `step_index` field on `RecipeIngredient` (nullable integer, 0-based, referencing the index in `Recipe.steps` JSON array). Recipes imported without step-ingredient mapping default to NULL.

**Pantry cross-reference:** The inventory-aware features that differentiate FreshUp:
- Recipe cards show "All ingredients in stock" badge when every required ingredient is in inventory.
- Recipe detail shows per-ingredient "in stock" badges and a pantry check summary.
- "Show what I can make now" toggle on the recipe browse page filters all content by ingredient availability.
- "Add missing to list" button calculates the delta between recipe ingredients and inventory, adding missing items to the grocery list in one tap.

**Household context over ratings:** Generic star ratings are replaced with personalized household data: "Cooked 7 times" (from `Recipe.times_cooked`), "In Sarah's favs" (from `UserRecipeRelation.is_liked`), and eventually "Top voted this week" (Phase 3 voting data). Passive voice is used for shared resource references ("in stock" not "you have") to avoid shareability conflicts.

**"I Shopped" flow:** The primary grocery-to-inventory bridge. Default tab is receipt scanning (Phase 4 readiness, with fallback to "From grocery list" in Phase 1). Items from the grocery list are presented grouped by store with tappable storage location badges (smart defaults from purchase history). Checked items are bulk-added to inventory; unchecked items persist on the grocery list.

**Recipe ingestion library:** The `recipe-scrapers` Python library (MIT, 624+ supported sites including HelloFresh and Kitchen Sanctuary) will serve as the parsing engine for Phase 2C/2D. FreshUp builds the orchestration layer (rate limiting, dedup, ingredient string decomposition, validation UI) around it. The library handles HTML-to-structured-recipe extraction. See Section 6 for recipe source strategy.

**Implementation order:** Shell (routing, nav, auth) → Home screen → Recipe browse → Recipe detail → Pantry → Grocery list → "I Shopped" flow. Each screen builds on components from the previous one.

### 5.11 Recipe Engagement Model (added v1.1)

Users interact with recipes through three semantically distinct actions:

- **Bookmark** — "Save for later." Private utility. The user's personal queue of recipes to try. Bookmarked recipes can optionally be assigned to a Menu (see 5.13). Analogous to browser bookmarks or Spotify's "Save to Library."
- **Like** — "I endorse this." Public-facing curation. Visible on the user's profile and used to curate a personal "menu" of recipes they stand behind. Analogous to Instagram likes or Spotify's public playlists.
- **Rating** — Post-cook evaluation. **Only available after the user has logged at least one cook event for the recipe** (via `POST /recipes/{id}/cook`). Ratings include a 0–5 scale, optional photos (stored in MinIO), and optional text commentary (tips, modifications, warnings). Ratings are never available before cooking — this ensures they reflect actual experience, not aspiration.

All three actions are independent. A user can bookmark without liking, like without bookmarking, and rate without either (as long as they've cooked the recipe). All three actions trigger recipe persistence (see 5.12).

The existing `is_favorite` field on `UserRecipeRating` is replaced by `is_bookmarked` and `is_liked` on `UserRecipeRelation`. Existing `is_favorite=true` rows migrate to `is_bookmarked=true`.

### 5.12 Browse-Then-Persist Recipe Storage (added v1.1)

Recipes from external sources (scrapers, URL import) are stored in the Recipe table with `is_persisted = false`. This makes them browseable but ephemeral — a "browse cache."

**Persistence triggers:** A recipe transitions from `is_persisted = false` to `is_persisted = true` when any user:
- Bookmarks it
- Likes it
- Adds it to a meal plan

Once persisted, a recipe is permanent — it accumulates ratings, cook events, and household context data.

**Cleanup:** A scheduled task prunes non-persisted recipes older than a configurable TTL (default 7 days, controlled by `BROWSE_CACHE_TTL_DAYS` env var). This prevents the Recipe table from growing unboundedly with stale browse cache data.

**Cold start:** When the database has zero persisted recipes or a user has zero saves, the homepage and recipe browse page display non-persisted recipes from the browse cache as fallback content, labeled with generic titles ("Popular recipes.", "Quick weeknight meals.") rather than personalized rows.

**Scraper behavior change:** Scrapers no longer bulk-insert recipes as permanent entries. They write to the browse cache (`is_persisted = false`). Dedup logic accounts for persistence status — if a persisted recipe already exists, skip; if a non-persisted recipe was pruned, re-create on next scrape.

### 5.13 Menu System (added v1.1)

Menus are user-owned recipe collections — the FreshUp equivalent of playlists. They come in two flavors:

**Manual menus:** User creates a menu, gives it a name, and manually adds/removes recipes. No filter rules.

**Auto-generated menus:** The system analyzes the user's bookmarked and liked recipes to detect behavioral patterns, then creates menus for each pattern with sufficient signal (>= 3 saves matching the pattern). Patterns are detected across all recipe attributes: source type, cuisine tags, dietary tags, cook time ranges, and ingredient commonalities.

**User editability (required):** Auto-generated menus are fully editable:
- **Title:** User can rename (e.g., "Indian cuisine" → "Curry night favorites").
- **Filter rules:** User can narrow, expand, or completely rewrite the rules. Examples: add a tag filter to restrict "Indian cuisine" to "Indian sides"; add a calorie cap to make a "lite" version; expand from "Indian" to "Indian OR Asian" by switching match logic to `any` and adding a rule.
- **Manual overrides:** User can add recipes that don't match the filter (marked `manually_added`, immune to filter changes) or remove recipes that do match (marked `manually_removed`, suppressed on re-evaluation).

**Homepage rotation:** Auto-generated menus rotate into homepage carousel slots. The 2–3 menus with highest engagement (measured by menu opens + recipe-from-menu cook events) are shown. All menus are permanently accessible in a "My Menus" section regardless of homepage visibility.

### 5.14 Personalized Home Feed (added v1.1)

Each user's homepage is personalized based on their behavioral data. The feed is recomputed on page load with a 15-minute React Query stale time for caching. All scoring is deterministic SQL — no LLM involvement.

**Feed sections (in display order):**

1. **"Make this right now" slideshow** — Recipes the user can cook immediately based on current inventory (100% ingredient availability, or configurable threshold). Sorted by: ingredient freshness priority (expiring items first), familiar-first ranking, user preference. Top 10. Persisted recipes only.

2. **"On Repeat" playlist** — Recipes the user is currently into, derived from four weighted signals: viewed-but-not-cooked (0.25), high-frequency-cooked with recency bias (0.30), recently-highly-rated (0.25), genre/ingredient affinity expansion (0.20). Top 15, with light shuffling in positions 6–15.

3. **Personalized rows (3–4 max)** — Dynamic carousel rows derived from the user's strongest behavioral patterns across any recipe attribute (source type, tags, cuisine, cook time). Patterns require >= 3 saves to qualify. Row selection prefers diversity across attribute types. Rows include both saved recipes and browse cache recipes matching the pattern (for discovery).

4. **Source-specific rows (max 2)** — Dedicated rows for recipe sources with >= 5 user saves. "See all" expands to a browse page showing the user's saves from that source, plus additional browse cache recipes from the same source under a "Discover more" divider.

5. **Fallback rows** — Fill remaining slots when personalized data is insufficient. Content: global popularity rankings, quick meals, recently scraped recipes. Phase out as personalized rows fill in.

**Recipes are added to the database for everyone** (the Recipe table is shared), but **each user's home feed is specific to their own saves, schedule, dietary preferences, and behavioral signals.**

### 5.15 Auto-Draft Weekly Meal Plan (added v1.1)

Each week (configurable day/time, default Sunday 8am), the system generates a draft weekly meal plan for inspiration.

**Draft behavior:**
- Fills dinner slots (7 days). Optionally lunch slots if user has opted into lunch planning.
- Sources from Suggestion Engine priority queue (Section 5.2): expiring items first, then familiar recipes, then new suggestions.
- Weights by: variety (no cuisine repeats on consecutive days), dietary balance, ingredient overlap (batch-friendly grouping).
- Includes 1–2 "stretch" recipes from browse cache to introduce variety.
- **Draft recipes are never committed.** They appear as faded/greyed-out cards on the Plan page. No impact on grocery list or inventory reservations until the user explicitly confirms a recipe.

**Household vs. Personal plan toggle:** The Plan page shows two views:
- **Household plan:** Meals confirmed by the coordinator (or via Phase 3C voting). All members see the same schedule. Confirmed household meals show as full-color cards.
- **My plan:** The user's personal schedule. Includes household meals they've opted into, personal meals they've planned, and auto-draft suggestions.

**Per-meal opt-out:** For any household meal, each user can individually opt out. Opt-out adjusts auto-scaling (one fewer serving), adjusts grocery list (removes user-specific dietary variation ingredients if applicable), and frees the slot for personal planning.

**Visual treatment:**
- Confirmed meals: full-color recipe cards.
- Draft/suggested meals: faded/greyed-out recipe cards with accept/dismiss/swap actions, labeled "Suggested."
- Opted-out slots: "You opted out" with "Plan something" browse link.

---

## 6. Recipe Source Strategy

### 6.1 HelloFresh Physical Cards (Primary — Batch Ingestion)

- A thick binder of HelloFresh recipe cards collected over ~2 years of subscription use.
- Cards have a highly consistent format — same layout, font, structure every time.
- Ingestion: photograph with iPad camera → upload to server → Ollama LLM parses structured recipe data.
- Expected accuracy: high, due to format consistency. OCR + LLM parsing should handle these reliably.
- This is the highest-volume initial recipe source.

### 6.2 HelloFresh Website (Ongoing Scraper)

- HelloFresh maintains a free recipe hub at hellofresh.com/recipes with 2,500+ recipes accessible without a subscription.
- Recipes include structured ingredient lists, step-by-step instructions, nutritional info, and allergen tags.
- Scraper targets JSON-LD structured data and/or HTML parsing of recipe pages.

### 6.3 Kitchen Sanctuary — kitchensanctuary.com (Ongoing Scraper)

- WordPress site using the WPRM (WordPress Recipe Maker) plugin.
- Recipes have JSON-LD structured data embedded in every recipe page — machine-readable ingredients, steps, cook times, servings, and nutrition.
- Scraping is straightforward: extract the JSON-LD block from each recipe page.
- Well-organized category structure (by cuisine, method, course) enables targeted scraping.

### 6.4 URL Import (On-Demand)

- Users paste a recipe URL; the system attempts JSON-LD extraction first, falls back to HTML parsing.
- Most major recipe sites use Schema.org Recipe markup, making this broadly compatible.
- Supports adding recipes from any source the user discovers.

### 6.5 Photo Upload (On-Demand)

- For handwritten cards, cookbook pages, or screenshots.
- Upload via web UI → Ollama LLM parses the image into structured recipe data.
- May require a second pass for handwriting recognition on handwritten cards.

### 6.6 Ad-Hoc Creation (On-Demand)

- User-created recipes built from inventory selections (see Section 5.5).
- The organic growth path for the recipe database — capturing what the household actually cooks.

### 6.7 Browse-Then-Persist Model (added v1.1)

All recipe sources above (except ad-hoc creation, which is always persisted) now follow the browse-then-persist pattern described in Section 5.12. Scraped and imported recipes enter the database with `is_persisted = false` and become permanent only when a user takes action (bookmark, like, or add to meal plan). This prevents the database from accumulating thousands of recipes that no household member has expressed interest in.

**Scrapers (6.2, 6.3) run periodically** (configurable, default weekly) to refresh the browse cache. **URL import (6.4) and photo upload (6.5)** also create non-persisted entries by default, though these are typically immediately bookmarked by the importing user, triggering persistence.

**See `docs/implementation-plan-recipe-engagement.md`** for detailed migration instructions affecting the existing scraper codebase.

---

## 7. Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| **Server OS** | Ubuntu Server (on Dell laptop, headless) | Lightweight, purpose-built for server workloads. Familiar from existing VM automation experience. |
| **Backend Framework** | Python / FastAPI | Async-capable, modern, excellent ecosystem for ML/LLM integration. |
| **Database** | SQLite via SQLAlchemy ORM | Zero-config, file-based, sufficient for household scale. ORM enables painless migration to Postgres. |
| **Local LLM** | Ollama (Llama 3 8B or similar) | Free, local, private. 32GB Dell RAM supports 7B+ models comfortably. |
| **Object Storage** | MinIO (local, S3-compatible) | Stores recipe images and receipt scans. S3 API compatibility enables seamless AWS migration. |
| **Frontend** | React (hooks, no Redux) + Tailwind CSS | Component-based state management for complex interactive UI. Tailwind for rapid styling. |
| **Containerization** | Docker + docker-compose | Environment parity, reproducible builds, AWS ECS migration path. |
| **OCR** | Tesseract (initial extraction) + Ollama (intelligent parsing) | Tesseract provides raw text; LLM handles messy formatting and semantic understanding. |
| **Voice (Future)** | Whisper (STT) + Piper (TTS) + OpenWakeWord | All open-source, all local. Wyoming protocol or custom integration. |
| **Voice Hardware (Future)** | Raspberry Pi 5 + USB mic + speaker | Dedicated always-on voice endpoint. ~$80-100 total hardware cost. |

---

## 8. Phase Plan

Each phase produces a usable increment of the system. Phases are broken into clearly bounded development areas to enable focused issue generation and coordinated execution via Sharkrite.

---

### Phase 1 — Foundation

**Goal:** A working household kitchen app with manual inventory management, recipe storage, grocery lists, and user profiles. Usable daily from phones and the iPad.

**Development Areas:**

#### 1A: Infrastructure & DevOps
- Dell laptop Ubuntu Server installation and headless configuration (lid close → do nothing, SSH access, static local IP)
- Docker and docker-compose setup
- MinIO local instance for image storage
- CI-friendly project structure with environment-based config (`.env`)

#### 1B: Database & ORM
- SQLAlchemy models for all entities defined in Section 4
- Alembic migration setup for schema versioning
- Seed data utilities (initial stores, common ingredient categories, unit types)

#### 1C: Authentication & User Management
- User registration and login (session-based or JWT — lightweight, no OAuth needed for household use)
- User profile management: dietary profiles, allergies, disliked ingredients, favorite ingredients, preferred substitutions
- Role assignment (coordinator vs. member)
- Per-user session on shared devices (iPad kitchen terminal shows "who are you?" selector)

#### 1D: Inventory Management API & UI
- Full CRUD for inventory items (add, view, edit, delete)
- Home screen quick actions: "I shopped" (search-and-select), "I froze/thawed items" (storage location update), "I ate snacks" (decrement checklist)
- Inventory filtering and search (by category, storage location, expiration status, shareability)
- Staple threshold configuration and restock alerts
- Store-ingredient mapping (preferred store, available-at stores)
- Shareability controls (shared / reserved / personal) with reservation notes

#### 1E: Recipe Management API & UI
- Full CRUD for recipes (manual creation, edit, delete)
- Ad-hoc recipe creation from inventory selections
- Recipe browsing with filters (cuisine, dietary compatibility, cook time, source)
- Per-user favorites and ratings
- Variation group support in recipe data model (dietary forks)
- Recipe detail view with ingredient list, steps, and nutritional info

#### 1F: Grocery List API & UI
- Manual add/remove grocery list items
- Per-store grouping based on ingredient-store mapping
- Per-user attribution ("Sarah added this for Saturday's cheesecake")
- Purchase check-off with inventory auto-update option
- Shared real-time list accessible from all household phones

#### 1G: PreparedFood Tracking
- Log leftovers and batch prep items after cooking
- Component ingredient tracking (stock blocks, onion pucks, etc.)
- PreparedFood browsing view ("what's in the fridge/freezer that's ready to eat?")
- Snack suggestion view (standalone snack items + shared open leftovers)

**Phase 1 Deliverable:** A fully functional web app for multi-user household kitchen management with manual data entry. Accessible from phones and iPad via browser.

---

### Phase 2 — Recipe Ingestion

**Goal:** Populate the recipe database at scale through automated parsing of HelloFresh cards, web scraping, and URL import.

**Note on Execution Order:** While the development areas below are numbered 2A-2D for logical grouping, the recommended execution order differs to prioritize immediate value and manage Ollama dependencies efficiently:

1. **2C (Web Scrapers)** — No Ollama dependency; provides immediate recipe database population
2. **2A (Ollama Integration Layer)** — LLM infrastructure setup required for subsequent OCR work
3. **4A (Costco Digital Receipts)** — Receipt ingestion solves a daily pain point; execute before card OCR
4. **4B (Paper Receipt OCR)** — Extends receipt pipeline to physical receipts
5. **2B (HelloFresh Card OCR)** — Physical cards are static; can be deferred without urgency
6. **2D (URL Import & Photo Upload)** — Most URL imports succeed via `recipe-scrapers` wild_mode without LLM

**Rationale:** This order delivers functional value sooner (populated recipe database via 2C, receipt-to-inventory automation via 4A/4B) while deferring lower-urgency OCR work (2B card digitization). The HelloFresh card binder isn't going anywhere; receipt ingestion solves a daily workflow friction point.

**Development Areas:**

#### 2A: Ollama Integration Layer
- Ollama API client (HTTP requests to `localhost:11434`)
- LLM abstraction layer (model-agnostic interface so models can be swapped)
- Prompt templates for recipe parsing (card OCR, photo parsing)
- Response validation and structured output extraction

#### 2B: HelloFresh Card OCR Pipeline
- iPad camera upload flow (photo → server)
- Tesseract OCR for initial text extraction
- Ollama LLM for intelligent parsing of OCR output into structured Recipe data
- Validation UI: user reviews and corrects parsed recipe before saving
- Batch processing support for working through the binder efficiently

#### 2C: Web Scrapers
- HelloFresh recipe hub scraper (JSON-LD extraction + HTML fallback)
- Kitchen Sanctuary scraper (WPRM JSON-LD extraction)
- Rate limiting and polite scraping practices
- Deduplication (don't re-import recipes already in the database)

#### 2D: URL Import & Photo Upload
- Generic URL recipe importer (JSON-LD extraction → HTML parsing fallback)
- Photo upload pipeline for handwritten cards and cookbook pages
- Ollama LLM parsing for unstructured recipe photos

**Phase 2 Deliverable:** A rich recipe database populated from all defined sources with automated and semi-automated ingestion pipelines.

---

### Phase 2.5 — Recipe Engagement & Personalized Feed (added v1.1)

**Goal:** Transform FreshUp from a kitchen utility into a daily-use app by introducing recipe engagement semantics (bookmark/like/rate), personalized homepage feeds, recipe collections (menus), and auto-draft meal planning.

**Prerequisite:** Phase 1 backend, Phase 2C (scrapers), Phase 2A (Ollama). Does not require Phase 2B or 2D.

**Detailed implementation plan:** See `docs/implementation-plan-recipe-engagement.md` for full specifications, data model schemas, API endpoints, query logic, and Sharkrite directives.

**Development Areas:**

#### 2.5A: Data Model & Migration
- Rename `UserRecipeRating` → `UserRecipeRelation` with bookmark/like split (Section 5.11)
- Add `is_persisted` flag to Recipe model (Section 5.12)
- New models: Menu, MenuRecipe, UserCookEvent, UserRecipeView
- Alembic migration with data migration (`is_favorite` → `is_bookmarked`)
- Update all model references across routers, schemas, and tests

#### 2.5B: Scraper Architecture Overhaul
- Modify existing scrapers to write `is_persisted = false`
- Implement persistence trigger on bookmark/like/meal-plan-add
- Implement cleanup job for expired non-persisted recipes
- Update dedup logic to account for persistence status

#### 2.5C: Feed Engine (Backend)
- `GET /feed/home` endpoint with per-user personalized payload
- "Make This Right Now" inventory-aware query
- "On Repeat" weighted behavioral signal scoring
- Dynamic personalized row pattern detection
- Source-specific row generation
- Cold start fallback logic

#### 2.5D: Menu System (Backend)
- Menu CRUD endpoints
- Auto-generated menu creation from behavioral patterns
- Filter rule evaluation engine (match/any logic across recipe attributes)
- Manual override tracking (manually_added / manually_removed)
- User-editable filter rules, titles, and organization

#### 2.5E: Meal Plan Draft & Schedule (Backend)
- Auto-draft generation (weekly, configurable schedule)
- Household vs. personal plan data separation
- Per-meal opt-out with scaling/grocery adjustment
- Draft → confirmed transition (only confirmed entries affect grocery list)

#### 2.5F: Frontend — Recipe Engagement UI
- Bookmark and like buttons on RecipeCard and RecipeDetail (replacing is_favorite)
- "I cooked this" button on RecipeDetail (creates UserCookEvent)
- Rating UI gated by cook event existence
- View tracking (fire-and-forget on recipe detail open)

#### 2.5G: Frontend — Home Feed & Browse
- Dynamic homepage from `GET /feed/home` (replace static sections)
- "Make This Right Now" hero slideshow
- "On Repeat" carousel
- Personalized + source-specific rows
- Source row "See all" → browse page with cached recipe expansion

#### 2.5H: Frontend — Menus
- "My Menus" section accessible from profile or recipe browse
- Menu detail page with recipe grid
- Menu filter rule editor UI
- Menu title and description editing

#### 2.5I: Frontend — Plan Page
- Weekly calendar view (replace Phase 3 stub)
- Household vs. personal plan toggle
- Auto-draft recipe cards (faded/greyed-out treatment)
- Accept/dismiss/swap actions on draft entries
- Per-meal opt-out toggle on household meals

**Phase 2.5 Deliverable:** A daily-driver recipe engagement experience where users browse, save, organize, cook, and rate recipes with a personalized home feed that encourages cooking — not just saving.

---

### Phase 3 — Smart Meal Planning

**Goal:** Intelligent recipe suggestions, democratic weekly meal planning with household voting, auto-scaling, and daily reconciliation.

**Note (v1.1):** Phase 2.5 introduces a lighter auto-draft meal plan and the "Make This Right Now" inventory-aware feed. Phase 3A's Suggestion Engine builds on the behavioral signals and feed queries established in 2.5C. Phase 3C's Democratic Meal Planning extends the Plan page calendar built in 2.5I with the full voting flow. The auto-draft feature is not replaced — it continues as the single-user experience alongside the multi-user voting system.

**Development Areas:**

#### 3A: Suggestion Engine
- Freshness-first priority queue (Section 5.2)
- Familiar-first ranking (weighted by cook frequency and user ratings)
- Inventory-aware filtering (suggest recipes that use what's available)
- Dietary profile filtering (per opted-in users, including variation suggestions)
- Substitution suggestions with in-stock prioritization
- Favorite ingredient boosting per participating user
- "Show me something new" escape hatch

#### 3B: Recipe Auto-Scaling & Variations
- Auto-scale recipe ingredients based on opted-in user count
- "Make extra" toggle with extra servings count and purpose note
- Split-recipe rendering: per-user variation view based on dietary assignments
- Grocery list generation that accounts for base ingredients + all active variations

#### 3C: Democratic Meal Planning
- Weekly meal plan voting flow (Section 5.6): candidate generation → individual ranking → draft generation → coordinator review → publication
- Voting UI: browse candidates, rank, add notes, flag hard vetoes, suggest additions
- Aggregate ranking algorithm (weighted by dietary constraints, inventory optimization, and user preference balance)
- Coordinator dashboard: review votes, adjust draft, approve/reject
- Opt-in/opt-out per meal with self-service alternative meal planning for opt-outs

#### 3D: Daily Reconciliation & Consumption Tracking
- Daily check-in prompts (Section 5.7): meal confirmation, snack logging, expiration alerts
- Inventory auto-decrement on meal confirmation
- PreparedFood creation on leftover logging
- Consumption data aggregation per user (foundation for future calorie/macro tracking)

**Phase 3 Deliverable:** A smart, collaborative meal planning system that reduces weekly meal coordination to a simple vote-and-approve flow.

---

### Phase 4 — Receipt Parsing

**Goal:** Automated inventory population from grocery receipts, starting with digital and progressing to paper OCR.

**Development Areas:**

#### 4A: Costco Digital Receipt Pipeline (First Target)
- Costco app receipt data extraction (format analysis, parsing logic)
- Receipt → structured item list (name, quantity, price, date, store)
- Inventory auto-population with user review/confirmation step
- Store parsing profile for Costco

#### 4B: Paper Receipt OCR Pipeline
- iPad camera receipt capture flow
- Tesseract OCR → raw text extraction
- Ollama LLM for intelligent parsing (store-aware, using parsing profiles)
- Store-specific parsing profiles for each of the 3-4 regular stores
- Few-shot prompt examples per store for Ollama
- Validation UI: user reviews and corrects parsed items before inventory update

#### 4C: Consumption Pattern Learning
- Purchase and depletion event tracking
- Average interval and consistency score calculation (after 3+ cycles)
- Proactive restock suggestion notifications (frequency + consistency gated)
- User confirmation required for all suggestions (no auto-additions)

#### 4D: Receipt Module Abstraction
- Design receipt parsing as a modular, reusable component
- Clean input/output interface (image or text in → structured item list out)
- Suitable for potential reuse in a future standalone price-tracking product

**Phase 4 Deliverable:** Automated grocery-to-inventory pipeline that closes the loop: shop → scan receipt → inventory updates → meal plan adjusts.

---

### Phase 5 — Voice Interface

**Goal:** Hands-free kitchen interaction via a dedicated voice endpoint.

**Development Areas:**

#### 5A: Voice Hardware Setup
- Raspberry Pi 5 with USB microphone and speaker
- Network configuration (WiFi connection to home server)
- Audio input/output testing and optimization

#### 5B: Speech Processing
- Whisper (local) for speech-to-text
- Piper (local) for text-to-speech
- OpenWakeWord for wake word detection (custom wake word, e.g., "Hey FreshUp")

#### 5C: VoiceAdapter Abstraction
- Pluggable voice interface: local Whisper (Pi), Safari Web Speech API (iPad/phone), future cloud STT
- All implementations conform to the same interface so the backend is voice-source agnostic

#### 5D: Conversational Interaction Layer
- Natural language intent parsing via Ollama
- Context carryover within a conversation session (multi-turn dialogue)
- Voice-specific commands mapped to API operations:
  - "Out of tomatoes and onions" → inventory update + grocery list prompt
  - "What should we eat tonight?" → suggestion engine query
  - "Add sesame oil to the list" → grocery list update
  - "Push meatballs to Thursday" → meal plan reschedule
- Defrost time awareness, schedule awareness, inventory awareness in responses
- Speaker identification as a stretch goal (voiceprint matching, or simple verbal identification for MVP)

**Phase 5 Deliverable:** A voice-controlled kitchen assistant that runs entirely on local hardware with zero cloud dependency for audio processing.

---

### Phase 6 — Mobile & Cloud

**Goal:** Access FreshUp from anywhere via mobile-optimized web app or native mobile app, backed by cloud infrastructure.

**Development Areas:**

#### 6A: Responsive / Mobile Optimization
- Mobile-first responsive redesign of React web UI (or React Native mobile app)
- Touch-optimized interactions for phone-sized screens
- Offline-capable grocery list (works in-store without home WiFi)

#### 6B: AWS Cloud Deployment
- Detailed AWS infrastructure design (separate design document — deferred)
- Likely: ECS/Fargate for API containers, RDS Postgres, S3 for object storage, KMS for customer-managed encryption keys
- Tailscale VPN as lightweight alternative to full cloud deployment

#### 6C: External Access & Sync
- Secure external access to FreshUp from outside the home network
- Data sync between local Dell server and cloud instance (if hybrid architecture)

**Phase 6 Deliverable:** FreshUp accessible from anywhere, with production-grade cloud infrastructure and privacy maintained via CMK encryption.

---

## 9. Known Tradeoffs

| Decision | Tradeoff | Mitigation |
|---|---|---|
| Local-first hosting | App unavailable if Dell is off or network is down | Cloud deployment in Phase 6; Dell on UPS for power resilience |
| SQLite for MVP | No concurrent write support; single-household only | SQLAlchemy abstraction enables Postgres migration when needed |
| Paper receipt OCR | Accuracy will vary; thermal paper degrades | Costco digital receipts as first target; validation UI for all parsed receipts; LLM improves over time with few-shot examples |
| React over Vanilla JS | Higher initial learning investment | Pays off at Phase 3 complexity; React Native path to mobile |
| No voice in MVP | Missing the "wow factor" feature initially | Push-to-talk via Safari Web Speech API available as interim if desired |
| Familiar-first suggestions | Could create a "filter bubble" of the same meals | Explicit "show me something new" escape hatch; periodic novelty injection configurable |

---

## 10. Future Vision (Out of Scope — Not Designed)

The following ideas were generated during brainstorming and are documented for future consideration. They do not affect the current architecture and should not influence MVP decisions.

- **Social recipe platform:** User-generated recipe photos, upvoting, captions with tips/substitutions, highest-rated photo as recipe preview, following other users/creators, community variations of recipes.
- **Household labor division assistant:** Tracking who bought ingredients, who cooked, who cleaned. Labor-weighted democracy in meal planning based on contributions.
- **Costco grocery ordering integration:** Automated order placement through the Costco app/website to complete the convenience loop.
- **Standalone price-tracking product:** Crowdsourced receipt data for tracking what different stores charge for products over time. Reuses the receipt parsing module built in Phase 4. Product normalization across stores is a significant unsolved challenge.
- **Passive calorie and macro tracking:** Per-user approximate daily nutritional tracking derived from meal consumption logging. Foundation data (nutritional info per recipe, consumption events per user) is captured in the data model; display and analysis is deferred.
- **Custom voice device product:** A dedicated FreshUp voice assistant device sold as an optional add-on. Hardware business considerations (manufacturing, support, firmware) make this a separate venture.
- **Seasonal and sale awareness:** Integrating store circular data or seasonal ingredient databases to improve suggestion timing and cost optimization.

---

## 11. Open Questions

| Question | Impacts | Resolution Timeline |
|---|---|---|
| AWS infrastructure design details (ECS vs. Lambda, RDS sizing, S3 lifecycle policies) | Phase 6 | Separate design document before Phase 6 begins |
| Specific Ollama model selection for receipt parsing vs. conversational features | Phase 2, 4 | Resolved during OCR spike (pre-Phase 2) |
| Costco digital receipt format and extraction method | Phase 4A | Investigate during Phase 4 planning |
| Offline grocery list strategy for in-store use without home WiFi | Phase 6A | Service worker / PWA approach likely; design during Phase 6 |
| React Native vs. responsive PWA for mobile | Phase 6A | Evaluate based on Phase 1-3 web UI complexity |
| HelloFresh scraping legal/ToS considerations | Phase 2C | Review terms of service before building scraper |
| Wake word selection and training for OpenWakeWord | Phase 5B | Custom wake word training during Phase 5 |
| Multi-household support (if product expands beyond single household) | Post-Phase 6 | Tenant isolation design; not needed for personal use |

---

## 12. Appendix: Development Area Index

For Sharkrite issue generation, each development area maps to a focused set of issues:

**Recommended Execution Order:** While the table below shows logical dependencies and sequential numbering, the recommended execution order for Phases 2 and 4 differs to prioritize immediate-value work and manage dependencies efficiently. Execute in this order: **2C → 2A → 4A → 4B → 2.5A–I → 2B → 2D**. See Section 8 (Phase 2 — Recipe Ingestion) for detailed rationale. Phase 2.5 (Recipe Engagement) should be completed before Phase 3 as it establishes behavioral signals and feed infrastructure that Phase 3A depends on. See `docs/implementation-plan-recipe-engagement.md` for Phase 2.5 detail.

| Code | Area | Phase | Dependencies |
|---|---|---|---|
| 1A | Infrastructure & DevOps | 1 | None |
| 1B | Database & ORM | 1 | 1A |
| 1C | Authentication & User Management | 1 | 1B |
| 1D | Inventory Management | 1 | 1B, 1C |
| 1E | Recipe Management | 1 | 1B, 1C |
| 1F | Grocery List | 1 | 1B, 1C, 1D |
| 1G | PreparedFood Tracking | 1 | 1B, 1C, 1D |
| 2A | Ollama Integration Layer | 2 | 1A |
| 2B | HelloFresh Card OCR | 2 | 2A, 1E |
| 2C | Web Scrapers | 2 | 1E |
| 2D | URL Import & Photo Upload | 2 | 2A, 1E |
| 2.5A | Data Model & Migration | 2.5 | 1B, 1E |
| 2.5B | Scraper Architecture Overhaul | 2.5 | 2C, 2.5A |
| 2.5C | Feed Engine (Backend) | 2.5 | 2.5A, 2.5B |
| 2.5D | Menu System (Backend) | 2.5 | 2.5A |
| 2.5E | Meal Plan Draft & Schedule (Backend) | 2.5 | 2.5A, 1F |
| 2.5F | Frontend: Recipe Engagement UI | 2.5 | 2.5A, 1-FE |
| 2.5G | Frontend: Home Feed & Browse | 2.5 | 2.5C, 2.5F |
| 2.5H | Frontend: Menus | 2.5 | 2.5D, 2.5F |
| 2.5I | Frontend: Plan Page | 2.5 | 2.5E, 2.5F |
| 3A | Suggestion Engine | 3 | 1D, 1E, 1G, 2.5C |
| 3B | Recipe Auto-Scaling & Variations | 3 | 1E, 1F |
| 3C | Democratic Meal Planning | 3 | 3A, 3B, 1C, 2.5I |
| 3D | Daily Reconciliation | 3 | 1D, 1G, 3C |
| 4A | Costco Digital Receipts | 4 | 1D, 2A |
| 4B | Paper Receipt OCR | 4 | 2A, 4A |
| 4C | Consumption Pattern Learning | 4 | 1D, 4A or 4B |
| 4D | Receipt Module Abstraction | 4 | 4A, 4B |
| 5A | Voice Hardware Setup | 5 | 1A |
| 5B | Speech Processing | 5 | 5A |
| 5C | VoiceAdapter Abstraction | 5 | 5B |
| 5D | Conversational Interaction | 5 | 5C, 2A, 3A |
| 6A | Mobile Optimization | 6 | Phase 1-3 complete |
| 6B | AWS Cloud Deployment | 6 | Separate design doc |
| 6C | External Access & Sync | 6 | 6B |

---

*This ADR captures the architectural decisions, rationale, and implementation plan for FreshUp as of 2026-03-13, amended 2026-05-03 (v1.1: Recipe Engagement & Personalized Feed). It is intended to be expanded into actionable issue sets per development area using Sharkrite.*