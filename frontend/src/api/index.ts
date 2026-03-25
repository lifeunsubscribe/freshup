/**
 * API client barrel export.
 *
 * Re-exports all API client functionality for convenient imports:
 * - Client utilities (apiClient, auth token management)
 * - TypeScript types
 * - React Query hooks for all domains
 */

// Client utilities
export {
  apiClient,
  setAuthToken,
  getAuthToken,
  clearAuthToken,
  isAuthenticated,
  getApiBaseUrl,
  ApiException,
  type ApiError,
} from './client';

// Types
export * from './types';

// Auth hooks
export {
  useLogin,
  useRegister,
  useLogout,
  useCurrentUser,
  useUpdateProfile,
  useChangePassword,
  useSwitchUser,
  authKeys,
} from './hooks/useAuth';

// Inventory hooks
export {
  useInventoryList,
  useInventoryItem,
  useLowStockAlerts,
  useCreateInventoryItem,
  useUpdateInventoryItem,
  useDeleteInventoryItem,
  useConsumeInventoryItem,
  useFreezeInventoryItem,
  useThawInventoryItem,
  useSetPreferredStore,
  useClearPreferredStore,
  useAddAvailableStore,
  useRemoveAvailableStore,
  useUpdateShareability,
  inventoryKeys,
  type InventoryListFilters,
} from './hooks/useInventory';

// Recipe hooks
export {
  useRecipeList,
  useRecipe,
  useCreateRecipe,
  useCreateAdHocRecipe,
  useUpdateRecipe,
  useDeleteRecipe,
  useAddRecipeIngredient,
  useUpdateRecipeIngredient,
  useDeleteRecipeIngredient,
  useRateRecipe,
  useMyRecipeRating,
  useDeleteMyRecipeRating,
  useRecipeAggregateRatings,
  recipeKeys,
  type RecipeListFilters,
} from './hooks/useRecipes';

// Grocery hooks
export {
  useGroceryList,
  useGroceryListByStore,
  useGroceryItem,
  useCreateGroceryItem,
  useUpdateGroceryItem,
  useDeleteGroceryItem,
  usePurchaseGroceryItem,
  useUnpurchaseGroceryItem,
  useBulkPurchaseGroceryItems,
  groceryKeys,
  type GroceryListFilters,
} from './hooks/useGrocery';

// Prepared foods hooks
export {
  usePreparedFoodList,
  usePreparedFood,
  useCreatePreparedFood,
  useUpdatePreparedFood,
  useDeletePreparedFood,
  useConsumePreparedFood,
  useFreezePreparedFood,
  useThawPreparedFood,
  useTransferPreparedFood,
  preparedFoodsKeys,
  type PreparedFoodListFilters,
} from './hooks/usePreparedFoods';

// Substitution hooks
export {
  useSubstitutionList,
  useCreateSubstitution,
  useUpdateSubstitution,
  useDeleteSubstitution,
  substitutionKeys,
} from './hooks/useSubstitutions';

// User hooks
export {
  useUsers,
  usersKeys,
} from './hooks/useUsers';
