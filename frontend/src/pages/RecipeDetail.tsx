import { useState } from 'react'
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
import { useRecipe, useMyRecipeRating, useRateRecipe } from '../api/hooks/useRecipes'
import { useAuth } from '../contexts/AuthContext'

export default function RecipeDetail() {
  const { id } = useParams<{ id: string }>()
  const { currentUser } = useAuth()

  const [activeTab, setActiveTab] = useState<TabType>('ingredients')
  const [selectedServings, setSelectedServings] = useState<2 | 4 | 6>(2)
  const [favoriteError, setFavoriteError] = useState<string | null>(null)

  const { data: recipe, isLoading: isLoadingRecipe, isError: isRecipeError } = useRecipe(id!, {
    enabled: !!id,
  })

  const { data: myRating, isLoading: isLoadingRating } = useMyRecipeRating(id!, {
    enabled: !!id,
    retry: false,
  })

  const rateRecipeMutation = useRateRecipe()

  const handleFavoriteToggle = async () => {
    if (!id) return

    setFavoriteError(null)

    try {
      // Toggle favorite status via rate endpoint (upsert behavior)
      // Preserve existing rating value while toggling is_favorite
      await rateRecipeMutation.mutateAsync({
        recipeId: id,
        data: {
          rating: myRating?.rating || 0,
          is_favorite: !myRating?.is_favorite,
        },
      })
    } catch (error) {
      console.error('Failed to toggle favorite:', error)
      setFavoriteError('Failed to update favorite status. Please try again.')
      // Clear error after 5 seconds
      setTimeout(() => {
        setFavoriteError(null)
      }, 5000)
    }
  }

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
    : 1

  const cookTime = recipe.cook_time_minutes
  const prepTime = recipe.prep_time_minutes
  const totalTime = (cookTime || 0) + (prepTime || 0)

  const isFavorited = myRating?.is_favorite || false

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
            {isFavorited && currentUser && (
              <Pill variant="success">In {currentUser.name}'s favs</Pill>
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
          />

          <TabBar activeTab={activeTab} onTabChange={setActiveTab} />

          <div>
            {activeTab === 'ingredients' && (
              <IngredientsTab
                ingredients={recipe.ingredients}
                servingsMultiplier={servingsMultiplier}
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
        {favoriteError && (
          <div className="fixed bottom-20 left-4 right-4 bg-red-50 border border-red-200 rounded-lg p-3 shadow-lg z-40">
            <p className="text-sm text-red-800">{favoriteError}</p>
          </div>
        )}
        <ActionBar
          isFavorited={isFavorited}
          onFavoriteToggle={handleFavoriteToggle}
          onAddToMealPlan={handleAddToMealPlan}
          isLoading={rateRecipeMutation.isPending || isLoadingRating}
        />
      </>
    </>
  )
}
