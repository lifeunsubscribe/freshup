import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import PageContainer from '../components/layout/PageContainer'
import RecipeHeader from '../components/recipe/RecipeHeader'
import ServingsControl from '../components/recipe/ServingsControl'
import TabBar, { TabType } from '../components/recipe/TabBar'
import IngredientsTab from '../components/recipe/IngredientsTab'
import CookTab from '../components/recipe/CookTab'
import NutritionTab from '../components/recipe/NutritionTab'
import ActionBar from '../components/recipe/ActionBar'
import Pill from '../components/ui/Pill'
import { useRecipe } from '../api/hooks/useRecipes'
import {
  useMyRecipeRelation,
  useToggleBookmark,
  useToggleLike,
} from '../api/hooks/useRecipeEngagement'
import { useInventoryList } from '../api/hooks/useInventory'
import { checkIngredientAvailability } from '../utils/pantryMatcher'
import { useAuth } from '../contexts/AuthContext'

export default function RecipeDetail() {
  const { id } = useParams<{ id: string }>()
  const { currentUser } = useAuth()

  const [activeTab, setActiveTab] = useState<TabType>('ingredients')
  const [engagementError, setEngagementError] = useState<string | null>(null)

  const { data: recipe, isLoading: isLoadingRecipe, isError: isRecipeError } = useRecipe(id!, {
    enabled: !!id,
  })

  const { data: myRelation, isLoading: isLoadingRelation } = useMyRecipeRelation(id!, {
    enabled: !!id,
    retry: false,
  })

  const { data: inventoryItems = [], isLoading: isLoadingInventory, isError: isInventoryError } = useInventoryList({})

  const toggleLike = useToggleLike()
  const toggleBookmark = useToggleBookmark()

  // Default to recipe's base_servings if it's one of the valid options (2, 4, 6)
  // Otherwise default to 2
  const defaultServings = recipe?.base_servings && [2, 4, 6].includes(recipe.base_servings)
    ? (recipe.base_servings as 2 | 4 | 6)
    : 2

  const [selectedServings, setSelectedServings] = useState<2 | 4 | 6>(defaultServings)

  // Update selectedServings when recipe loads or changes
  // This ensures the correct default is set after the recipe data arrives
  useEffect(() => {
    if (recipe?.base_servings && [2, 4, 6].includes(recipe.base_servings)) {
      setSelectedServings(recipe.base_servings as 2 | 4 | 6)
    }
  }, [recipe?.base_servings])

  /**
   * Run a bookmark or like toggle, surfacing failures in the detail page banner.
   *
   * These go through the dedicated toggle endpoints rather than POST /rate.
   * /rate is a whole-relation upsert, so driving a button through it rewrote
   * every other field — the previous implementation here sent
   * `rating: myRating?.rating || 0`, which turned an unrated recipe into one
   * rated zero every time the user tapped the heart.
   */
  const runToggle = async (
    mutateAsync: (vars: { recipeId: string; next: boolean }) => Promise<unknown>,
    next: boolean,
    failureMessage: string
  ) => {
    if (!id) return

    setEngagementError(null)

    try {
      await mutateAsync({ recipeId: id, next })
    } catch (error) {
      console.error(failureMessage, error)
      setEngagementError(failureMessage)
      setTimeout(() => setEngagementError(null), 5000)
    }
  }

  const handleLikeToggle = () =>
    runToggle(toggleLike.mutateAsync, !isLiked, 'Could not update like. Please try again.')

  const handleBookmarkToggle = () =>
    runToggle(
      toggleBookmark.mutateAsync,
      !isBookmarked,
      'Could not update bookmark. Please try again.'
    )

  const handleAddToMealPlan = () => {
    // Phase 2 feature: Add to meal plan functionality
  }

  if (isLoadingRecipe) {
    return (
      <PageContainer>
        <div className="py-8 text-center text-text-secondary">
          Loading recipe...
        </div>
      </PageContainer>
    )
  }

  if (isRecipeError || !recipe) {
    return (
      <PageContainer>
        <div className="py-8 text-center">
          <p className="text-text-primary font-medium mb-2">Recipe not found</p>
          <p className="text-text-secondary">The recipe you're looking for doesn't exist or has been removed.</p>
        </div>
      </PageContainer>
    )
  }

  // Calculate servings multiplier based on recipe's base servings
  // Example: if base_servings=4 and selectedServings=2, multiplier=0.5 (scale down)
  // Example: if base_servings=4 and selectedServings=6, multiplier=1.5 (scale up)
  // Guard against division by zero - default to 1 (no scaling) if base_servings is invalid
  const servingsMultiplier = recipe.base_servings > 0
    ? selectedServings / recipe.base_servings
    : (() => {
        if (import.meta.env.DEV) {
          console.warn(`Invalid base_servings value (${recipe.base_servings}) for recipe ${recipe.id}. Defaulting to no scaling (multiplier=1).`)
        }
        return 1
      })()

  const cookTime = recipe.cook_time_minutes
  const prepTime = recipe.prep_time_minutes
  const totalTime = (cookTime || 0) + (prepTime || 0)

  const isLiked = myRelation?.is_liked ?? false
  const isBookmarked = myRelation?.is_bookmarked ?? false

  // Calculate missing ingredients for "Add missing to list" button
  const stockStatus = recipe
    ? checkIngredientAvailability(recipe.ingredients, inventoryItems)
    : { inStock: [], outOfStock: [], totalCount: 0, inStockCount: 0 }

  return (
    <>
      <PageContainer>
        <div className="pb-24">
          <RecipeHeader
            title={recipe.name}
            subtitle={recipe.notes || undefined}
            imageUrl={recipe.source_image || undefined}
          />

          <div className="mb-4 flex flex-wrap gap-2">
            {isLiked && currentUser && (
              <Pill variant="success">{currentUser.name} likes this</Pill>
            )}
            {isBookmarked && (
              <Pill variant="default">Saved</Pill>
            )}
            {totalTime > 0 && (
              <Pill variant="default">{totalTime} min</Pill>
            )}
            {recipe.tags.map((tag) => (
              <Pill key={tag} variant="default">{tag}</Pill>
            ))}
          </div>

          <ServingsControl
            selectedServings={selectedServings}
            onServingsChange={setSelectedServings}
            baseServings={recipe.base_servings}
          />

          <TabBar activeTab={activeTab} onTabChange={setActiveTab} />

          <div>
            {activeTab === 'ingredients' && (
              <IngredientsTab
                ingredients={recipe.ingredients}
                servingsMultiplier={servingsMultiplier}
                inventoryItems={inventoryItems}
                stockStatus={stockStatus}
                inventoryError={isInventoryError}
              />
            )}
            {activeTab === 'cook' && (
              <CookTab
                steps={recipe.steps}
                ingredients={recipe.ingredients}
                servingsMultiplier={servingsMultiplier}
              />
            )}
            {activeTab === 'nutrition' && (
              <NutritionTab nutritionalInfo={recipe.nutritional_info} />
            )}
          </div>
        </div>
      </PageContainer>

      <>
        {engagementError && (
          <div className="fixed bottom-20 left-4 right-4 bg-red-50 border border-red-200 rounded-lg p-3 shadow-lg z-40">
            <p className="text-sm text-red-800">{engagementError}</p>
          </div>
        )}
        {isInventoryError && (
          <div className="fixed bottom-20 left-4 right-4 bg-yellow-50 border border-yellow-200 rounded-lg p-3 shadow-lg z-40">
            <p className="text-sm text-yellow-800">Unable to load pantry inventory. The "Add missing to list" button is temporarily unavailable.</p>
          </div>
        )}
        <ActionBar
          isLiked={isLiked}
          onLikeToggle={handleLikeToggle}
          isBookmarked={isBookmarked}
          onBookmarkToggle={handleBookmarkToggle}
          onAddToMealPlan={handleAddToMealPlan}
          isLoading={isLoadingRelation || isLoadingInventory || isInventoryError}
          missingIngredients={stockStatus.outOfStock}
        />
      </>
    </>
  )
}
