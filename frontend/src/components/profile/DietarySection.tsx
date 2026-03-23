import { useState, useEffect } from 'react'
import { useUpdateProfile } from '../../api/hooks/useAuth'

interface DietarySectionProps {
  currentProfiles: string[]
}

const DIETARY_OPTIONS = [
  { value: 'omnivore', label: 'Omnivore' },
  { value: 'vegetarian', label: 'Vegetarian' },
  { value: 'vegan', label: 'Vegan' },
  { value: 'pescatarian', label: 'Pescatarian' },
  { value: 'keto', label: 'Keto' },
  { value: 'low_carb', label: 'Low Carb' },
  { value: 'low_sugar', label: 'Low Sugar' },
]

/**
 * DietarySection component for managing dietary preferences
 *
 * Features:
 * - Multi-select checkboxes for dietary profiles
 * - Save button with loading/success states
 * - Error handling for save failures
 * - Resets to current values on cancel
 */
export default function DietarySection({ currentProfiles }: DietarySectionProps) {
  const [selectedProfiles, setSelectedProfiles] = useState<string[]>(currentProfiles)
  const [hasChanges, setHasChanges] = useState(false)
  const updateProfile = useUpdateProfile()

  useEffect(() => {
    setSelectedProfiles(currentProfiles)
  }, [currentProfiles])

  useEffect(() => {
    const changed =
      JSON.stringify([...selectedProfiles].sort()) !==
      JSON.stringify([...currentProfiles].sort())
    setHasChanges(changed)
  }, [selectedProfiles, currentProfiles])

  const toggleProfile = (value: string) => {
    if (selectedProfiles.includes(value)) {
      setSelectedProfiles(selectedProfiles.filter((p) => p !== value))
    } else {
      setSelectedProfiles([...selectedProfiles, value])
    }
  }

  const handleSave = async () => {
    try {
      await updateProfile.mutateAsync(
        { dietary_profile: selectedProfiles },
        {
          onSuccess: () => {
            // Reset hasChanges state after successful save
            setHasChanges(false)
          },
        }
      )
    } catch (error) {
      console.error('Failed to update dietary preferences:', error)
    }
  }

  const handleCancel = () => {
    setSelectedProfiles(currentProfiles)
  }

  return (
    <div className="bg-white rounded-card border border-warm-border p-6">
      <h2 className="text-xl font-semibold text-text-primary mb-4">
        Dietary Preferences
      </h2>
      <p className="text-sm text-text-secondary mb-4">
        Select all dietary preferences that apply to you
      </p>

      {/* Checkbox grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
        {DIETARY_OPTIONS.map((option) => (
          <label
            key={option.value}
            className="flex items-center gap-3 p-3 rounded-button border border-warm-border hover:bg-cream-dark cursor-pointer transition-colors"
          >
            <input
              type="checkbox"
              checked={selectedProfiles.includes(option.value)}
              onChange={() => toggleProfile(option.value)}
              className="w-4 h-4 text-olive border-warm-border rounded focus:ring-2 focus:ring-olive focus:ring-offset-2 cursor-pointer"
            />
            <span className="text-text-primary font-medium">{option.label}</span>
          </label>
        ))}
      </div>

      {/* Error message */}
      {updateProfile.isError && (
        <div className="mb-4 rounded-button border border-terra bg-terra/10 p-3">
          <p className="text-sm text-terra-dark">
            {updateProfile.error instanceof Error
              ? updateProfile.error.message
              : 'Failed to update dietary preferences. Please try again.'}
          </p>
        </div>
      )}

      {/* Success message */}
      {updateProfile.isSuccess && !hasChanges && (
        <div className="mb-4 rounded-button border border-olive bg-olive/10 p-3">
          <p className="text-sm text-olive-dark">Dietary preferences saved successfully!</p>
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
