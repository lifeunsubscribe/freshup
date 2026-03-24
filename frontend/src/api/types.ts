/**
 * TypeScript type definitions matching backend Pydantic schemas.
 *
 * These types mirror the response/request schemas from the FastAPI backend.
 */

// ============================================================================
// Enums
// ============================================================================

export enum UserRole {
  COORDINATOR = 'coordinator',
  MEMBER = 'member',
}

export enum DietaryProfile {
  VEGETARIAN = 'vegetarian',
  VEGAN = 'vegan',
  GLUTEN_FREE = 'gluten_free',
  DAIRY_FREE = 'dairy_free',
  KOSHER = 'kosher',
  HALAL = 'halal',
}

export enum Category {
  PRODUCE = 'produce',
  DAIRY = 'dairy',
  PROTEIN = 'protein',
  GRAINS = 'grains',
  CONDIMENTS = 'condiments',
  SNACKS = 'snacks',
  BEVERAGES = 'beverages',
  FROZEN = 'frozen',
  CANNED = 'canned',
  BAKING = 'baking',
  SPICES = 'spices',
  OTHER = 'other',
}

export enum StorageLocation {
  PANTRY = 'pantry',
  FRIDGE = 'fridge',
  FREEZER = 'freezer',
  COUNTER = 'counter',
}

export enum Shareability {
  SHARED = 'shared',
  RESERVED = 'reserved',
  PERSONAL = 'personal',
}

export enum SourceType {
  MANUAL = 'manual',
  HELLOFRESH_CARD = 'hellofresh_card',
  AD_HOC = 'ad_hoc',
}

export enum PreparedFoodType {
  COMPLETE_MEAL = 'complete_meal',
  BATCH_PORTION = 'batch_portion',
  COMPONENT_INGREDIENT = 'component_ingredient',
}

export enum GrocerySource {
  MANUAL = 'manual',
  LOW_STOCK = 'low_stock',
  RECIPE = 'recipe',
}

// ============================================================================
// Auth Types
// ============================================================================

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserResponse {
  id: string;
  name: string;
  email: string;
  role: string;
  dietary_profile: string[];
  allergies: string[];
  disliked_ingredients: string[];
  favorite_ingredients: string[];
  failed_login_attempts: number;
  lockout_until: string | null;
  lockout_count: number;
}

export interface UserCreate {
  name: string;
  email: string;
  password: string;
  dietary_profile?: string[];
  allergies?: string[];
  disliked_ingredients?: string[];
  favorite_ingredients?: string[];
  role?: string;
}

export interface UserUpdate {
  name?: string;
  dietary_profile?: string[];
  allergies?: string[];
  disliked_ingredients?: string[];
  favorite_ingredients?: string[];
}

export interface PasswordChangeRequest {
  old_password: string;
  new_password: string;
}

export interface SwitchUserRequest {
  user_id: string;
}

export interface UserListResponse {
  id: string;
  name: string;
  role: string;
  dietary_profile: string[];
  allergies: string[];
  disliked_ingredients: string[];
  favorite_ingredients: string[];
}

// ============================================================================
// Inventory Types
// ============================================================================

export interface StoreResponse {
  id: string;
  name: string;
  has_digital_receipts: boolean;
}

export interface InventoryItemCreate {
  name: string;
  quantity: number;
  unit: string;
  category: string;
  storage_location: string;
  added_by: string;
  expiration_date?: string;
  frozen_date?: string;
  is_staple?: boolean;
  minimum_threshold?: number;
  shareability?: string;
  reserved_note?: string;
  price?: number;
  brand?: string;
  preferred_store?: string;
  vegan_friendly?: boolean;
}

export interface InventoryItemUpdate {
  name?: string;
  quantity?: number;
  unit?: string;
  category?: string;
  storage_location?: string;
  expiration_date?: string | null;
  frozen_date?: string | null;
  is_staple?: boolean;
  minimum_threshold?: number | null;
  shareability?: string;
  reserved_note?: string | null;
  price?: number | null;
  brand?: string | null;
  preferred_store?: string | null;
  vegan_friendly?: boolean;
}

export interface InventoryItemResponse {
  id: string;
  name: string;
  quantity: number;
  unit: string;
  category: string;
  storage_location: string;
  added_by: string;
  date_added: string;
  expiration_date: string | null;
  frozen_date: string | null;
  is_staple: boolean;
  minimum_threshold: number | null;
  shareability: string;
  reserved_note: string | null;
  reserved_for: string | null;
  price: number | null;
  brand: string | null;
  preferred_store: string | null;
  preferred_store_rel: StoreResponse | null;
  available_at_stores: StoreResponse[];
  vegan_friendly: boolean;
}

export interface InventoryItemListResponse {
  id: string;
  name: string;
  quantity: number;
  unit: string;
  category: string;
  storage_location: string;
  date_added: string;
  expiration_date: string | null;
  is_staple: boolean;
  shareability: string;
}

export interface LowStockAlertItem {
  id: string;
  name: string;
  quantity: number;
  unit: string;
  minimum_threshold: number;
  deficit: number;
}

export interface ConsumptionRequest {
  amount?: number;
  delete_when_empty?: boolean;
}

export interface ConsumptionResponse {
  message: string;
  deleted: boolean;
  item: InventoryItemResponse | null;
}

export interface ThawRequest {
  destination?: string;
}

export interface SetPreferredStoreRequest {
  store_id: string;
}

export interface AddAvailableStoreRequest {
  store_id: string;
}

export interface UpdateShareabilityRequest {
  shareability: string;
  reserved_note?: string;
}

// ============================================================================
// Recipe Types
// ============================================================================

export interface RecipeIngredientResponse {
  id: string;
  recipe_id: string;
  ingredient_name: string;
  quantity: number;
  unit: string;
  step_index: number | null;
}

export interface RecipeIngredientCreate {
  ingredient_name: string;
  quantity: number;
  unit: string;
  step_index?: number;
}

export interface RecipeIngredientUpdate {
  ingredient_name?: string;
  quantity?: number;
  unit?: string;
  step_index?: number | null;
}

export interface RecipeResponse {
  id: string;
  name: string;
  source_type: string;
  source_image: string | null;
  steps: string[];
  created_by: string | null;
  created_at: string;
  notes: string | null;
  tags: string[];
  cook_time_minutes: number | null;
  prep_time_minutes: number | null;
  base_servings: number;
  hellofresh_card_id: string | null;
  variation_groups: Record<string, unknown> | null;
  nutritional_info: Record<string, unknown> | null;
  ingredients: RecipeIngredientResponse[];
}

export interface RecipeListResponse {
  id: string;
  name: string;
  source_type: string;
  created_at: string;
  tags: string[];
  cook_time_minutes: number | null;
  prep_time_minutes: number | null;
  base_servings: number;
}

export interface RecipeCreate {
  name: string;
  source_type: string;
  steps: string[];
  notes?: string;
  tags?: string[];
  cook_time_minutes?: number;
  prep_time_minutes?: number;
  hellofresh_card_id?: string;
  variation_groups?: Record<string, unknown>;
}

export interface RecipeUpdate {
  name?: string;
  source_type?: string;
  steps?: string[];
  notes?: string | null;
  tags?: string[];
  cook_time_minutes?: number | null;
  prep_time_minutes?: number | null;
  hellofresh_card_id?: string | null;
  variation_groups?: Record<string, unknown> | null;
}

export interface InventoryItemUsage {
  inventory_item_id: string;
  quantity_used: number;
  unit: string;
  step_index?: number;
}

export interface AdHocRecipeCreate {
  name: string;
  steps: string[];
  notes?: string;
  tags?: string[];
  inventory_items: InventoryItemUsage[];
  decrement_inventory?: boolean;
}

export interface UserRecipeRatingCreate {
  rating: number;
  is_favorite?: boolean;
  notes?: string;
}

export interface UserRecipeRatingResponse {
  id: string;
  user_id: string;
  recipe_id: string;
  rating: number;
  is_favorite: boolean;
  notes: string | null;
  rated_at: string;
}

export interface RecipeAggregateRatingsResponse {
  average_rating: number | null;
  rating_count: number;
  favorite_count: number;
}

// ============================================================================
// Grocery Types
// ============================================================================

export interface GroceryItemCreate {
  item_name: string;
  quantity: number;
  unit: string;
  source: string;
  target_store?: string;
}

export interface GroceryItemUpdate {
  item_name?: string;
  quantity?: number;
  unit?: string;
  target_store?: string | null;
}

export interface GroceryItemResponse {
  id: string;
  item_name: string;
  quantity: number;
  unit: string;
  source: string;
  added_by: string;
  date_added: string;
  purchased: boolean;
  purchased_by: string | null;
  purchased_date: string | null;
  target_store: string | null;
}

export interface BulkPurchaseRequest {
  item_ids: string[];
  create_inventory_item?: boolean;
  storage_location?: string;
  category?: string;
}

export interface BulkPurchaseResponse {
  items: GroceryItemResponse[];
  inventory_items_created: number;
}

export interface StoreGroceryGroup {
  store_id: string;
  store_name: string;
  items: GroceryItemResponse[];
}

export interface StoreGroupedGroceryResponse {
  stores: StoreGroceryGroup[];
  unassigned: GroceryItemResponse[];
}

// ============================================================================
// Prepared Food Types
// ============================================================================

export interface PreparedFoodCreate {
  name: string;
  type: string;
  servings: number;
  storage_location: string;
  date_prepared: string;
  estimated_expiration?: string;
  recipe_id?: string;
  shareability?: string;
  reserved_note?: string;
}

export interface PreparedFoodUpdate {
  name?: string;
  type?: string;
  servings?: number;
  storage_location?: string;
  date_prepared?: string;
  estimated_expiration?: string | null;
  recipe_id?: string | null;
  shareability?: string;
  reserved_note?: string | null;
}

export interface PreparedFoodResponse {
  id: string;
  name: string;
  type: string;
  servings: number;
  servings_remaining: number;
  storage_location: string;
  prepared_by: string;
  date_prepared: string;
  estimated_expiration: string | null;
  recipe_id: string | null;
  shareability: string;
  reserved_note: string | null;
  reserved_for: string | null;
}

export interface PreparedFoodListResponse {
  id: string;
  name: string;
  type: string;
  servings_remaining: number;
  storage_location: string;
  date_prepared: string;
  estimated_expiration: string | null;
  shareability: string;
}

export interface PreparedFoodConsumptionResponse {
  message: string;
  deleted: boolean;
  item: PreparedFoodResponse | null;
}

export interface TransferRequest {
  storage_location: string;
}

// ============================================================================
// Substitution Types
// ============================================================================

export interface ReplacementItem {
  ingredient: string;
  rank: number;
}

export interface SubstitutionPreferenceCreate {
  original_ingredient: string;
  replacements: ReplacementItem[];
  context?: string;
}

export interface SubstitutionPreferenceUpdate {
  replacements?: ReplacementItem[];
  context?: string;
}

export interface SubstitutionPreferenceResponse {
  id: string;
  user_id: string;
  original_ingredient: string;
  replacements: ReplacementItem[];
  context: string | null;
}
