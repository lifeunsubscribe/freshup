import { useState, useEffect, KeyboardEvent } from 'react'
import { X } from 'lucide-react'
import { useUpdateProfile } from '../../api/hooks/useAuth'

interface AllergiesSectionProps {
  currentAllergies: string[]
}

/**
 * AllergiesSection component for managing food allergies
 *
 * Features:
 * - Tag input for freeform allergy entry
 * - Removable tags with X button
 * - Enter key to add new allergy
 * - Save/cancel buttons for changes
 * - Input validation and error handling
 */
export default function AllergiesSection({ currentAllergies }: AllergiesSectionProps) {
  const [allergies, setAllergies] = useState<string[]>(currentAllergies)
  const [inputValue, setInputValue] = useState('')
  const [hasChanges, setHasChanges] = useState(false)
  const updateProfile = useUpdateProfile()

  useEffect(() => {
    setAllergies(currentAllergies)
  }, [currentAllergies])

  useEffect(() => {
    const changed =
      JSON.stringify([...allergies].sort()) !== JSON.stringify([...currentAllergies].sort())
    setHasChanges(changed)
  }, [allergies, currentAllergies])

  const handleAddAllergy = () => {
    const trimmed = inputValue.trim()
    if (trimmed && !allergies.includes(trimmed)) {
      setAllergies([...allergies, trimmed])
      setInputValue('')
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleAddAllergy()
    }
  }

  const handleRemoveAllergy = (allergyToRemove: string) => {
    setAllergies(allergies.filter((a) => a !== allergyToRemove))
  }

  const handleSave = async () => {
    try {
      await updateProfile.mutateAsync({ allergies })
    } catch (error) {
      console.error('Failed to update allergies:', error)
    }
  }

  const handleCancel = () => {
    setAllergies(currentAllergies)
    setInputValue('')
  }

  return (
    <div className="bg-white rounded-card border border-warm-border p-6">
      <h2 className="text-xl font-semibold text-text-primary mb-4">Allergies</h2>
      <p className="text-sm text-text-secondary mb-4">
        Add any food allergies or intolerances
      </p>

      {/* Input field */}
      <div className="mb-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type an allergy and press Enter"
            className="flex-1 px-4 py-2 rounded-button border border-warm-border focus:outline-none focus:ring-2 focus:ring-olive focus:border-transparent"
          />
          <button
            onClick={handleAddAllergy}
            disabled={!inputValue.trim()}
            className="px-6 py-2 rounded-button bg-olive text-cream font-medium hover:bg-olive-dark focus:outline-none focus:ring-2 focus:ring-olive focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Add
          </button>
        </div>
      </div>

      {/* Tags list */}
      {allergies.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-6">
          {allergies.map((allergy) => (
            <div
              key={allergy}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-terra/10 text-sm text-terra border border-terra/20"
            >
              <span>{allergy}</span>
              <button
                onClick={() => handleRemoveAllergy(allergy)}
                className="hover:bg-terra/20 rounded-full p-0.5 transition-colors"
                aria-label={`Remove ${allergy}`}
              >
                <X size={14} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {allergies.length === 0 && (
        <div className="mb-6 p-4 rounded-button bg-cream-dark border border-warm-border">
          <p className="text-sm text-text-secondary text-center">
            No allergies added yet. Use the input above to add allergies.
          </p>
        </div>
      )}

      {/* Error message */}
      {updateProfile.isError && (
        <div className="mb-4 rounded-button border border-terra bg-terra/10 p-3">
          <p className="text-sm text-terra-dark">
            {updateProfile.error instanceof Error
              ? updateProfile.error.message
              : 'Failed to update allergies. Please try again.'}
          </p>
        </div>
      )}

      {/* Success message */}
      {updateProfile.isSuccess && !hasChanges && (
        <div className="mb-4 rounded-button border border-olive bg-olive/10 p-3">
          <p className="text-sm text-olive-dark">Allergies saved successfully!</p>
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
