# FreshUp — Design System & Frontend Reference

**Project:** FreshUp — Privacy-First Kitchen Management System  
**Author:** Sarah + Design Session (2026-03-23)  
**Status:** Phase 1-FE Implementation Reference  
**Companion to:** `docs/FreshUp-ADR.md` (architecture), this file covers visual design, component patterns, and frontend-specific decisions.

---

## 1. Design Philosophy

FreshUp should feel like a warm, organized kitchen — not a tech product. The UI is inspired by Mealime's approach: clean, un-intimidating, appetizing, and cozy. Every screen should pass the "would we actually use this daily while cooking?" test.

**Core principles:**
- **Cozy, not clinical.** Warm earth tones, soft shapes, generous whitespace. No harsh blues, no SaaS gradients, no aggressive CTAs.
- **Triage-first.** Every screen leads with what needs attention (expiring items, tonight's dinner, low stock) before showing the full data set.
- **One-tap actions.** The most common operations (check off a grocery item, freeze something, log a snack) should never require navigation to a separate screen.
- **Passive voice for shared resources.** The pantry belongs to the household, not a user. Say "Jasmine rice is in stock" not "You have jasmine rice." Avoid possessives that could trigger shareability conflicts.
- **Personalized over generic.** Show "Cooked 7 times" and "In Sarah's favs" instead of star ratings. Household context is more useful than crowd-sourced scores.

---

## 2. Color Palette

### Primary Colors

| Role | Hex | Usage |
|------|-----|-------|
| **Olive green** (primary) | `#6b7f4a` | CTA buttons, active tab indicators, checkmarks, title period accent, nav active state, icon color |
| **Dark olive** (text on green) | `#4a6332` | Text labels paired with green elements (e.g., section headers, active tab text) |
| **Café mocha** (warm accent) | `#a08b6e` | Expiration alerts, "never cooked" labels, notification badges, favorite hearts, attention indicators |
| **Warm terracotta** (alert) | `#c2715a` | Low stock warnings, out-of-stock badges, urgent states only |

### Background & Surface Colors

| Role | Hex | Usage |
|------|-----|-------|
| **Page background** | `#faf8f4` | App-wide background (warm cream, NOT white, NOT grey) |
| **Card surface** | `#ffffff` | Cards, input fields, modal surfaces — white on cream creates depth without shadows |
| **Surface secondary** | `#f9f8f3` | Subtle card backgrounds (used sparingly for nested elements within cards) |
| **Icon background** | `#f0eee6` | Small icon containers, category chips background |
| **Ingredient pill bg** | `#f7f5ee` | Recipe ingredient pills, "in stock" badges |

### Border & Divider Colors

| Role | Hex | Usage |
|------|-----|-------|
| **Card border** | `#e8e5d8` | Card outlines, section dividers, input borders |
| **Mocha alert border** | `#e6ddd0` | Expiration alert card borders |
| **Subtle divider** | `#f0efe8` | Within-list item separators (lighter than card borders) |
| **Button border** | `#d4d0c0` | Secondary/outline button borders |

### Text Colors

| Role | Hex | Usage |
|------|-----|-------|
| **Primary text** | `#2c2c2a` | Headings, item names, primary content |
| **Secondary text** | `#8b8b7e` | Descriptions, metadata, timestamps, inactive tab labels |
| **Tertiary text** | `#a09f96` | Section labels (uppercase), collapsed category counts |
| **Muted text** | `#c4c3ba` | Checkbox borders (unchecked), very low-priority indicators |
| **Link/action text** | `#6b7f4a` | "See all", "View all", sort dropdown, interactive text |

### Alert-Specific Colors

| Role | Hex (bg) | Hex (text) | Usage |
|------|----------|------------|-------|
| **Expiring** | `#f5f0e8` | `#a08b6e` | Expiration warning backgrounds and labels |
| **Low stock** | `#faf0ed` | `#c2715a` | Low stock pill backgrounds and labels |

### Rules
- **No pure white backgrounds** on the page level. `#faf8f4` always.
- **No pure black text.** Darkest is `#2c2c2a`.
- **No blue, no purple, no neon.** The palette is exclusively warm earth tones.
- **No drop shadows.** White cards on cream background creates natural depth.
- **Accent colors are earned.** Olive green = action. Mocha = attention. Terracotta = urgency. If something isn't actionable, attention-worthy, or urgent, it gets a grey.

---

## 3. Typography

**Font:** System font stack (Anthropic Sans in mockups, but use `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif` in production for native feel on each platform).

| Element | Size | Weight | Color | Notes |
|---------|------|--------|-------|-------|
| Page title | 22px | 500 | `#2c2c2a` | Includes olive period accent: `<span style="color:#6b7f4a">.</span>` |
| Recipe title | 26px | 500 | `#2c2c2a` | Used on recipe detail view only |
| Section header | 15px | 500 | `#2c2c2a` | Carousel titles, card group headers. Includes olive period. |
| Category label | 12px | 400 | `#a09f96` | `text-transform: uppercase; letter-spacing: 0.06em` |
| Body text | 14-15px | 400 | `#2c2c2a` | Recipe steps use 15px for readability while cooking |
| Card title | 13px | 500 | `#2c2c2a` | Recipe card names in grid/carousel |
| Metadata | 12px | 400 | `#8b8b7e` | Cook time, servings, cuisine tags |
| Small metadata | 11px | 400 | `#8b8b7e` | Card sub-labels, "in stock" badges |
| Tiny labels | 10px | 400-500 | varies | Pill badges, "Cooked 7x", source labels |
| Nav labels | 10px | 400/500 | `#8b8b7e` / `#6b7f4a` | Bottom nav, inactive/active states |

### Rules
- **Two weights only:** 400 (regular) and 500 (medium). Never 600 or 700.
- **The olive period** (`.`) appears at the end of all page titles and carousel section headers. It's the brand mark.
- **Sentence case everywhere.** Never Title Case, never ALL CAPS except category labels.
- **Line height:** 1.3 for headings, 1.5-1.6 for body text, 1.4 for metadata.

---

## 4. Spacing & Layout

### Border Radius

| Element | Radius | Notes |
|---------|--------|-------|
| Cards | 12-14px | Larger for primary cards (tonight's dinner), 12px for grid cards |
| Buttons (primary) | 12px | CTAs, "Add to meal plan" |
| Buttons (secondary/small) | 8px | Filter chips, "Ate it", "Freeze" |
| Input fields | 10px | Search bars, text inputs |
| Pills/badges | 4-6px | "in stock", "low", source labels |
| Tag chips | 12px | Full-round for tags like "pescatarian", "japanese" |
| Images | 16px (hero), 10px (card), 8px (thumbnail) | |
| Bottom sheet | 14px top corners | Modal sheets slide up with rounded top |

### Spacing

| Context | Value | Notes |
|---------|-------|-------|
| Page horizontal padding | 16px | Phone-first (375px width target) |
| Between sections | 24-28px | Vertical rhythm between major groups |
| Between cards in grid | 10-12px | Gap in 2-column grid |
| Card internal padding | 12-16px | Larger for primary cards |
| Between list items | 2px (tight), 8px (cards) | Tight for inventory lists, spaced for alert cards |
| Within a list item | 8-10px vertical padding | |
| Icon container size | 32px (quick actions), 28px (store badges), 24px (inline) | |

### Grid

- **Recipe grid:** 2 columns, `gap: 12px`
- **Quick actions:** 2 columns, `gap: 10px`
- **Stat cards:** 3 columns, `gap: 8px`
- **Carousels:** Horizontal scroll, `gap: 10px`, cards at `min-width: 150px`

### Phone-First

- **Target width:** 375px (iPhone SE / standard Android)
- **Touch targets:** Minimum 44x44px for tappable elements
- **Bottom nav:** 5 tabs (Home, Plan, Recipes, Pantry, List)
- **Thumb zone:** Primary actions in bottom 2/3 of screen

---

## 5. Components

### 5.1 Recipe Card (Grid/Carousel)

Used in: recipe browse grid, carousels, search results, "ready to eat" horizontal scroll.

```
┌─────────────────┐
│  [4:3 image]    │  ← 4:3 aspect ratio, rounded top corners
│  ♥ (top-right)  │  ← Favorite heart overlay (mocha fill if favorited)
│  [source badge]  │  ← "HelloFresh", "My recipe" (top-left, optional)
│  [avail badge]   │  ← "All ingredients in stock" (bottom-left, optional, olive bg)
├─────────────────┤
│  Recipe name     │  ← 13px/500 (12px in carousel variant)
│  25 min · 4 srv · mexican │  ← Metadata line with cuisine tag
│  ✓ Cooked 12x   │  ← Household context (green) OR "Never cooked" (mocha)
└─────────────────┘
```

**Variants:**
- Grid card: `min-width` auto (fills 2-col grid)
- Carousel card: `min-width: 150px`, flex-shrink-0
- Last card in carousel: `opacity: 0.7` to hint scrollability

**Conditional elements:**
- Favorite heart: shown when `UserRecipeRating.is_favorite = true` for any household member
- Source badge: shown for imported recipes (`source_type != 'manual' && source_type != 'ad_hoc'`)
- Availability badge: shown when pantry cross-reference finds all ingredients in stock
- Variations badge: shown when `variation_groups` is not null/empty (e.g., "2 variations")

### 5.2 Recipe Detail View

**Tab order:** Ingredients (default) → Cook & enjoy! → Nutrition

**Ingredients tab (default):**
- Grouped by category (Fresh produce, Pantry, Protein, etc.)
- Each item shows name, quantity, and "in stock" badge if available in inventory
- Green dot indicator for items needing purchase, gold dot for pantry items
- Pantry check summary card at bottom (passive voice)
- Action bar: "Add to meal plan" (primary), "Add missing to list" (secondary), favorite heart

**Cook & enjoy! tab:**
- Steps with large numbered circles (olive green on cream background)
- Inline ingredient pills below each step (requires `step_index` on `RecipeIngredient`)
- Timer callout cards for steps with wait times (clock icon + duration)
- Optional per-step images (graceful absence — no placeholder when missing)
- Ingredients without a `step_index` show in a "General" group at the top

**Header elements:**
- Back navigation
- Recipe title with olive period accent
- Subtitle (e.g., "with ginger rice & avocado-cucumber salad")
- Personalized pills: "In Sarah's favs", "Cooked 7 times", cook time, cuisine tags
- Hero image (16px radius, 4:3 aspect)
- Servings selector (2/4/6 segmented control) + US/Metric toggle

### 5.3 Grocery List Item

Used in: grocery list (by-store and flat views), "I shopped" flow, home screen preview.

```
┌──────────────────────────────────────────┐
│ ☐/☑  Item name (quantity)    [context]   │
└──────────────────────────────────────────┘
```

- Checkbox: 18-20px, `border-radius: 5-6px`, olive fill when checked
- Item name: 13-14px primary text, quantity inline
- Context chip (right side): "sushi stacks" (recipe link), "staple restock" (source), "manual"
- Checked state: name gets `text-decoration: line-through; color: #a09f96`, shows who purchased
- By-store view: grouped under store headers with store initial badge

### 5.4 Inventory Item Row

Used in: pantry view (category-grouped list), "I ate snacks" checklist.

```
┌──────────────────────────────────────────┐
│  Item name  [expiry badge]    quantity   │
└──────────────────────────────────────────┘
```

- Item name: 14px primary text
- Expiry badge: mocha pill ("3d", "tomorrow")
- Low stock badge: terracotta pill ("low")
- Quantity: 12px secondary text, right-aligned
- Inline quick actions on expiring items: "Ate it", "Freeze" buttons

### 5.5 Quick Action Card

Used in: home screen quick actions grid.

```
┌─────────────────────┐
│ [icon container]     │  ← 32x32px, rounded 8px, cream bg
│                      │
│ Action title         │  ← 14px/500
│ Description text     │  ← 12px secondary
└─────────────────────┘
```

- 2-column grid
- White card on cream background
- Hover: card background shifts to `#f4f2ea`
- Icons: 18px, olive green stroke

### 5.6 Bottom Navigation Bar

5 tabs: Home, Plan, Recipes, Pantry, List

- White background, top border `1px solid #e8e5d8`
- Active state: olive green fill on icon, olive text, weight 500
- Inactive: `#8b8b7e` stroke icons, same color text
- List tab: mocha badge with item count (positioned top-right of icon)
- Icon size: 22x22px
- Label: 10px

### 5.7 Carousel Section

Used in: recipe browse page.

```
Section title.          See all →
Description text
┌───┐ ┌───┐ ┌───┐ ┌───┐
│   │ │   │ │   │ │ ░ │  ← last card faded (opacity 0.7)
└───┘ └───┘ └───┘ └───┘
        ← horizontal scroll →
```

- Title: 15px/500 with olive period
- Subtitle: 12px secondary
- "See all" link: 12px olive green, navigates to grid view with filter pre-applied
- Cards: horizontal scroll, `gap: 10px`, `overflow-x: auto`
- Sticky section nav bar (below search) for jumping between carousels

---

## 6. Screen Architecture

### Navigation

**Bottom tab bar (5 tabs):**

| Tab | Icon | Route | API Domain |
|-----|------|-------|------------|
| Home | House | `/` | Multiple (dashboard) |
| Plan | Calendar | `/plan` | MealPlanEntry, WeeklyMealPlanVote (Phase 3) |
| Recipes | Document | `/recipes` | Recipe, RecipeIngredient, UserRecipeRating |
| Pantry | Arrow/shelf | `/pantry` | InventoryItem, Store |
| List | Cart | `/grocery` | GroceryListItem |

### Screen Inventory

| Screen | Route | Description |
|--------|-------|-------------|
| Home | `/` | Dashboard: tonight's dinner, quick actions, expiration alerts, grocery preview, ready to eat |
| Recipe Browse | `/recipes` | Spotify-style carousels with sticky section nav. "Can make now" toggle. Search transitions to grid. |
| Recipe Grid | `/recipes?filter=...` | Filtered 2-column grid. Entered via "See all" or search. |
| Recipe Detail | `/recipes/:id` | Tabbed view: Ingredients (default) → Cook & enjoy! → Nutrition |
| Pantry | `/pantry` | Storage tabs, stat cards, expiring/low stock triage, collapsible category inventory |
| Grocery List | `/grocery` | By-store (default) and flat list views. Shared/global reads. |
| I Shopped | `/shopped` | Quick action flow: scan receipt (default tab), from grocery list, add manually |
| Profile | `/profile` | User preferences, dietary profile, allergies, substitution preferences |

### Recipe Browse → Grid Transition

The browse page (carousels) and grid page (filtered list) are two modes of the same route:
- Default: carousel view with section nav
- Activated: grid view, triggered by "See all" on any carousel OR search input OR filter selection
- Back: returns to carousel view

### "I Shopped" Flow

**Default tab: Scan receipt** (Phase 4 readiness — shows camera/upload prompt for Phase 1 with "coming soon" state, falls back to "From grocery list" as functional default until receipt scanning is implemented).

**"From grocery list" tab:**
1. Shows unchecked grocery items grouped by store
2. User checks off purchased items (each shows storage location badge)
3. Storage badges are tappable (cycle through fridge/freezer/pantry/counter)
4. Smart defaults: storage location based on previous purchases of same item
5. "Out of stock" items are left unchecked (stay on list for next trip)
6. "Select all" per store for bulk operations
7. Summary card: X of Y checked, progress bar
8. "Done — add X items to pantry" button → `POST /grocery/bulk-purchase` with `create_inventory_item=true`

---

## 7. Data-Driven UI Patterns

### Pantry Cross-Reference

The inventory-aware features that differentiate FreshUp from generic recipe apps:

- **Recipe detail "Pantry check":** Compares recipe ingredients against inventory. Shows "in stock" badges on matching items. Summary: "Jasmine rice and salt are in stock. 5 ingredients needed from the store."
- **"All ingredients in stock" badge:** Green pill on recipe cards where every required ingredient is in inventory.
- **"Show what I can make now" toggle:** Filters all recipe carousels/grids to only recipes with full ingredient availability.
- **"Add missing to list" button:** Calculates delta between recipe ingredients and inventory, adds missing items to grocery list in one tap.

### Personalized Household Context

Replace generic ratings with household-specific data:

| Data Source | Display | Location |
|-------------|---------|----------|
| `Recipe.times_cooked` | "Cooked 7x" (green checkmark) | Recipe cards, detail view pills |
| `UserRecipeRating.is_favorite` | "In Sarah's favs" (gold star) | Recipe detail view pills |
| `WeeklyMealPlanVote` (Phase 3) | "Top voted this week" | Recipe detail view pills |
| `MealPlanEntry` history | "Last made: March 15" | Recipe detail view |

### Smart Defaults

- **Storage location on grocery→inventory:** Based on previous purchases of the same item name
- **Servings selector:** Defaults to household size (count of active users)
- **Recipe sort:** "Most cooked" as default (familiar-first per ADR)
- **Grocery list default view:** By-store grouping (optimized for shopping trips)
- **Grocery list filter:** Unpurchased items only (active list, not historical log)

---

## 8. Implementation Notes

### Tech Stack

- **Framework:** React (hooks, no Redux) + Tailwind CSS
- **State management:** React Query or SWR for server state (caching, background refetch, optimistic updates). Local React state for UI-only state.
- **Routing:** React Router v6
- **Build:** Vite (fast dev server, optimized builds)
- **Target:** Mobile-first responsive (375px primary), served as static build from FastAPI

### Component Hierarchy

```
App
├── BottomNav (persistent, 5 tabs)
├── HomeScreen
│   ├── TonightsDinner (MealPlanEntry card)
│   ├── QuickActionsGrid (4 action cards)
│   ├── ExpirationAlerts (InventoryItem list)
│   ├── GroceryPreview (GroceryListItem summary)
│   └── ReadyToEat (PreparedFood carousel)
├── RecipeBrowse
│   ├── SearchBar
│   ├── CanMakeNowToggle
│   ├── SectionNav (sticky horizontal scroll)
│   └── RecipeCarousel (repeated per section)
│       └── RecipeCard (reusable)
├── RecipeGrid
│   ├── FilterChips
│   ├── SortDropdown
│   └── RecipeCard (reusable, 2-col grid)
├── RecipeDetail
│   ├── RecipeHeader (title, meta, hero image)
│   ├── ServingsControl
│   ├── TabBar (Ingredients | Cook & enjoy! | Nutrition)
│   ├── IngredientsTab (default)
│   │   ├── IngredientGroup (by category)
│   │   ├── PantryCheck (summary card)
│   │   └── ActionBar (add to plan, add missing, favorite)
│   └── CookTab
│       └── RecipeStep (number, text, inline ingredients, timer, optional image)
├── PantryView
│   ├── StorageTabs (All | Fridge | Freezer | Pantry)
│   ├── StatCards (total, expiring, low stock)
│   ├── ExpiringSection (with inline actions)
│   ├── LowStockSection (with progress bars)
│   └── CategoryGroup (collapsible, with item rows)
├── GroceryList
│   ├── ViewToggle (By store | All items)
│   ├── StoreGroup (with checkable items)
│   └── BulkPurchaseAction
└── IShoppedFlow
    ├── ModeSelector (Scan receipt | From list | Manual)
    ├── GroceryCheckoff (store-grouped with storage badges)
    └── PurchaseSummary (progress bar, confirm button)
```

### Key Reusable Components

- **RecipeCard:** Used in browse grid, carousels, search results, home screen
- **GroceryItem:** Used in grocery list, "I shopped" flow, home preview
- **InventoryRow:** Used in pantry category lists, "I ate snacks" checklist
- **StorageBadge:** Tappable badge cycling through fridge/freezer/pantry/counter
- **PantryCheck:** Inventory cross-reference summary (used in recipe detail and recipe cards)
- **SectionNav:** Sticky horizontal scroll bar for jumping between page sections

### API Integration Patterns

- **React Query** for all server state. Each API domain gets its own query key namespace.
- **Optimistic updates** for checkbox-style operations (grocery check-off, inventory consumption).
- **Polling** (30s interval) for grocery list shared state. Upgrade to SSE in Phase 3 if needed.
- **Prefetching:** When viewing recipe browse, prefetch recipe detail data on hover/long-press.

### Tailwind Custom Theme

```javascript
// tailwind.config.js extension
module.exports = {
  theme: {
    extend: {
      colors: {
        olive: {
          DEFAULT: '#6b7f4a',
          dark: '#4a6332',
        },
        mocha: {
          DEFAULT: '#a08b6e',
          light: '#f5f0e8',
          border: '#e6ddd0',
        },
        terra: {
          DEFAULT: '#c2715a',
          light: '#faf0ed',
        },
        cream: {
          DEFAULT: '#faf8f4',
          card: '#ffffff',
          surface: '#f9f8f3',
          icon: '#f0eee6',
          pill: '#f7f5ee',
        },
        warm: {
          border: '#e8e5d8',
          divider: '#f0efe8',
          'btn-border': '#d4d0c0',
        },
        text: {
          primary: '#2c2c2a',
          secondary: '#8b8b7e',
          tertiary: '#a09f96',
          muted: '#c4c3ba',
        }
      },
      borderRadius: {
        'card': '12px',
        'card-lg': '14px',
        'button': '12px',
        'button-sm': '8px',
        'input': '10px',
        'pill': '6px',
        'tag': '12px',
        'image-hero': '16px',
        'image-card': '10px',
      }
    }
  }
}
```

---

## 9. Design Decisions Log

| Decision | Rationale | Date |
|----------|-----------|------|
| Ingredients tab as default on recipe detail | Users browse recipes to assess "what do I need?" before committing to cook. Budget assessment first, cooking second. | 2026-03-23 |
| Inline ingredients per step (Cook tab) | Eliminates scroll-back-and-forth between ingredients list and steps. Requires `step_index` field on `RecipeIngredient`. | 2026-03-23 |
| Passive voice for pantry references | "In stock" not "you have" — avoids triggering shareability conflicts in multi-user household ("those were MY avocados"). | 2026-03-23 |
| Household context over star ratings | "Cooked 7x" and "In Sarah's favs" are more useful than anonymous 4.2-star ratings for a household app. Generic ratings only useful if comparing identical recipes across sources (future feature). | 2026-03-23 |
| Spotify-style carousel browse as default Recipes view | Surfaces smart playlists (favorites, quick meals, cuisine categories, recently added) without requiring users to construct filters manually. "See all" transitions to filtered grid. | 2026-03-23 |
| "Show what I can make now" toggle on Recipes | Short-term planning mode — filters all carousels by ingredient availability. Single toggle instead of a dedicated "Ready to cook" carousel (avoids redundancy). | 2026-03-23 |
| Scan receipt as default "I shopped" tab | Receipt scanning is the lowest-friction path from shopping to inventory update. Shows "coming soon" state in Phase 1-FE, functional in Phase 4. Falls back to "From grocery list" tab. | 2026-03-23 |
| Café mocha over gold/yellow for warm accent | Original gold (#c4a54a) rendered as "pukey mustard" on screen. Mocha (#a08b6e) provides same warmth without the sickly undertone. | 2026-03-23 |
| Warm cream (#faf8f4) page background | White backgrounds read as clinical. Cream reads as kitchen/parchment. White cards on cream creates depth without drop shadows. | 2026-03-23 |
| `step_index` on RecipeIngredient model | Required for inline-ingredients-per-step UI. Nullable integer (0-based). Existing recipes and imports default to NULL. Validation: must be < len(recipe.steps). | 2026-03-23 |
| `recipe-scrapers` library for Phase 2 | Python library (624+ sites, MIT license) handles HTML→recipe parsing. Covers HelloFresh and Kitchen Sanctuary. Eliminates custom scraper maintenance. FreshUp builds orchestration layer around it. | 2026-03-23 |
| Sticky section nav on recipe browse | Solves category navigation without mode-switching. Horizontal scrollable bar pinned below search. Tapping a section smooth-scrolls to that carousel. | 2026-03-23 |
| Personal vs household grocery list toggle | Deferred to implementation — needs design work for toggling between "my items" and "all household items." | 2026-03-23 |

---

*This design system captures decisions from the Phase 1-FE design session on 2026-03-23. It should be referenced by Claude Code during frontend implementation and updated as design decisions evolve through testing and iteration.*
