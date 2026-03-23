import { useState, useEffect, KeyboardEvent } from 'react'
import { X } from 'lucide-react'
import { useUpdateProfile } from '../../api/hooks/useAuth'

interface DislikedIngredientsSectionProps {
  currentDisliked: string[]
}

/**
 * DislikedIngredientsSection component for managing disliked ingredients
 *
 * Features:
 * - Tag input for freeform ingredient entry
 * - Removable tags with X button
 * - Enter key to add new ingredient
 * - Save/cancel buttons for changes
 * - Input validation and error handling
 */
export default function DislikedIngredientsSection({
  currentDisliked,
}: DislikedIngredientsSectionProps) {
  const [disliked, setDisliked] = useState<string[]>(currentDisliked)
  const [inputValue, setInputValue] = useState('')
  const [hasChanges, setHasChanges] = useState(false)
  const updateProfile = useUpdateProfile()

  useEffect(() => {
    setDisliked(currentDisliked)
  }, [currentDisliked])

  useEffect(() => {
    const changed =
      JSON.stringify([...disliked].sort()) !== JSON.stringify([...currentDisliked].sort())
    setHasChanges(changed)
  }, [disliked, currentDisliked])

  const handleAddIngredient = () => {
    const trimmed = inputValue.trim()
    if (trimmed && !disliked.includes(trimmed)) {
      setDisliked([...disliked, trimmed])
      setInputValue('')
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleAddIngredient()
    }
  }

  const handleRemoveIngredient = (ingredientToRemove: string) => {
    setDisliked(disliked.filter((i) => i !== ingredientToRemove))
  }

  const handleSave = async () => {
    try {
      await updateProfile.mutateAsync(
        { disliked_ingredients: disliked },
        {
          onSuccess: () => {
            // Reset hasChanges state after successful save
            setHasChanges(false)
          },
        }
      )
    } catch (error) {
      console.error('Failed to update disliked ingredients:', error)
    }
  }

  const handleCancel = () => {
    setDisliked(currentDisliked)
    setInputValue('')
  }

  return (
    <div className="bg-white rounded-card border border-warm-border p-6">
      <h2 className="text-xl font-semibold text-text-primary mb-4">
        Disliked Ingredients
      </h2>
      <p className="text-sm text-text-secondary mb-4">
        Add ingredients you prefer to avoid in recipes
      </p>

      {/* Input field */}
      <div className="mb-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type an ingredient and press Enter"
            maxLength={100}
            className="flex-1 px-4 py-2 rounded-button border border-warm-border focus:outline-none focus:ring-2 focus:ring-olive focus:border-transparent"
          />
          <button
            onClick={handleAddIngredient}
            disabled={!inputValue.trim()}
            className="px-6 py-2 rounded-button bg-olive text-cream font-medium hover:bg-olive-dark focus:outline-none focus:ring-2 focus:ring-olive focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Add
          </button>
        </div>
      </div>

      {/* Tags list */}
      {disliked.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-6">
          {disliked.map((ingredient) => (
            <div
              key={ingredient}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-mocha/10 text-sm text-mocha border border-mocha/20"
            >
              <span>{ingredient}</span>
              <button
                onClick={() => handleRemoveIngredient(ingredient)}
                className="hover:bg-mocha/20 rounded-full p-0.5 transition-colors"
                aria-label={`Remove ${ingredient}`}
              >
                <X size={14} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {disliked.length === 0 && (
        <div className="mb-6 p-4 rounded-button bg-cream-dark border border-warm-border">
          <p className="text-sm text-text-secondary text-center">
            No disliked ingredients added yet. Use the input above to add ingredients.
          </p>
        </div>
      )}

      {/* Error message */}
      {updateProfile.isError && (
        <div className="mb-4 rounded-button border border-terra bg-terra/10 p-3">
          <p className="text-sm text-terra-dark">
            {updateProfile.error instanceof Error
              ? updateProfile.error.message
              : 'Failed to update disliked ingredients. Please try again.'}
          </p>
        </div>
      )}

      {/* Success message */}
      {updateProfile.isSuccess && !hasChanges && (
        <div className="mb-4 rounded-button border border-olive bg-olive/10 p-3">
          <p className="text-sm text-olive-dark">Disliked ingredients saved successfully!</p>
        </div>
      )}

      {/* Action buttons */}
      {hasChanges && (
        <div className="flex gap-3">
          <button
            onClick={handleSave}
            disabled={updateProfile.isPending}
            className="px-6 py-2 rounded-button bg-olive text-cream font-medium hover:bg-olive-dark focus:outline-none focus:ring-2 focus:ring-olive focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {updateProfile.isPending ? 'Saving...' : 'Save Changes'}
          </button>
          <button
            onClick={handleCancel}
            disabled={updateProfile.isPending}
            className="px-6 py-2 rounded-button bg-cream-dark text-text-primary font-medium hover:bg-mocha/10 focus:outline-none focus:ring-2 focus:ring-mocha focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  )
}
