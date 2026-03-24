import { useState, FormEvent, useEffect } from 'react'
import { X, Plus, Edit2, Trash2, ArrowRight } from 'lucide-react'
import {
  useSubstitutionList,
  useCreateSubstitution,
  useUpdateSubstitution,
  useDeleteSubstitution,
} from '../../api/hooks/useSubstitutions'
import type { ReplacementItem, SubstitutionPreferenceResponse } from '../../api/types'

/**
 * SubstitutionsSection component for managing ingredient substitution preferences
 *
 * Features:
 * - List all substitution preferences (original → ranked replacements)
 * - Add new substitution with modal form
 * - Edit existing substitution with modal form
 * - Delete substitution with confirmation
 * - Ranked replacement list (1st, 2nd, 3rd choice)
 */
export default function SubstitutionsSection() {
  const [showAddModal, setShowAddModal] = useState(false)
  const [editingPreference, setEditingPreference] =
    useState<SubstitutionPreferenceResponse | null>(null)

  const { data: preferences = [], isLoading } = useSubstitutionList()
  const createMutation = useCreateSubstitution()
  const updateMutation = useUpdateSubstitution()
  const deleteMutation = useDeleteSubstitution()

  const handleDelete = async (id: string) => {
    if (window.confirm('Are you sure you want to delete this substitution preference?')) {
      await deleteMutation.mutateAsync(id)
    }
  }

  return (
    <div className="bg-white rounded-card border border-warm-border p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-xl font-semibold text-text-primary">
            Substitution Preferences
          </h2>
          <p className="text-sm text-text-secondary mt-1">
            Define your preferred ingredient replacements
          </p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-button bg-olive text-cream font-medium hover:bg-olive-dark focus:outline-none focus:ring-2 focus:ring-olive focus:ring-offset-2 transition-colors"
        >
          <Plus size={16} />
          Add Substitution
        </button>
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="p-4 text-center text-text-secondary">
          Loading substitution preferences...
        </div>
      )}

      {/* Error message for delete failures */}
      {deleteMutation.isError && (
        <div className="mb-4 rounded-button border border-terra bg-terra/10 p-3">
          <p className="text-sm text-terra-dark">
            {deleteMutation.error instanceof Error
              ? deleteMutation.error.message
              : 'Failed to delete substitution. Please try again.'}
          </p>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && preferences.length === 0 && (
        <div className="p-6 rounded-button bg-cream-dark border border-warm-border">
          <p className="text-sm text-text-secondary text-center">
            No substitution preferences yet. Click "Add Substitution" to create one.
          </p>
        </div>
      )}

      {/* Preferences list */}
      {!isLoading && preferences.length > 0 && (
        <div className="space-y-3">
          {preferences.map((pref) => (
            <div
              key={pref.id}
              className="p-4 rounded-button border border-warm-border hover:bg-cream-dark transition-colors"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="font-medium text-text-primary">
                      {pref.original_ingredient}
                    </span>
                    <ArrowRight size={16} className="text-text-tertiary" />
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {pref.replacements.map((replacement, idx) => (
                      <div
                        key={replacement.ingredient}
                        className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-olive/10 text-sm border border-olive/20"
                      >
                        <span className="font-medium text-olive">{idx + 1}.</span>
                        <span className="text-text-primary">{replacement.ingredient}</span>
                      </div>
                    ))}
                  </div>
                  {pref.context && (
                    <p className="text-xs text-text-tertiary mt-2">
                      Context: {pref.context}
                    </p>
                  )}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setEditingPreference(pref)}
                    className="p-2 rounded-button hover:bg-mocha/10 text-text-secondary hover:text-mocha transition-colors"
                    aria-label="Edit substitution"
                  >
                    <Edit2 size={16} />
                  </button>
                  <button
                    onClick={() => handleDelete(pref.id)}
                    disabled={deleteMutation.isPending}
                    className="p-2 rounded-button hover:bg-terra/10 text-text-secondary hover:text-terra transition-colors disabled:opacity-50"
                    aria-label="Delete substitution"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add/Edit Modal */}
      {(showAddModal || editingPreference) && (
        <SubstitutionModal
          preference={editingPreference}
          onClose={() => {
            setShowAddModal(false)
            setEditingPreference(null)
          }}
          onSave={async (data) => {
            try {
              if (editingPreference) {
                await updateMutation.mutateAsync({ id: editingPreference.id, data })
              } else {
                await createMutation.mutateAsync(data)
              }
              setShowAddModal(false)
              setEditingPreference(null)
            } catch (error) {
              console.error('Failed to save substitution:', error)
            }
          }}
          isSaving={createMutation.isPending || updateMutation.isPending}
        />
      )}
    </div>
  )
}

interface SubstitutionModalProps {
  preference: SubstitutionPreferenceResponse | null
  onClose: () => void
  onSave: (data: {
    original_ingredient?: string
    replacements: ReplacementItem[]
    context?: string
  }) => Promise<void>
  isSaving: boolean
}

function SubstitutionModal({
  preference,
  onClose,
  onSave,
  isSaving,
}: SubstitutionModalProps) {
  const [originalIngredient, setOriginalIngredient] = useState(
    preference?.original_ingredient || ''
  )
  const [replacements, setReplacements] = useState<ReplacementItem[]>(
    preference?.replacements || []
  )
  const [context, setContext] = useState(preference?.context || '')
  const [currentReplacement, setCurrentReplacement] = useState('')

  // Handle Escape key to close modal
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isSaving) {
        onClose()
      }
    }
    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [onClose, isSaving])

  const handleAddReplacement = () => {
    const trimmed = currentReplacement.trim()
    if (trimmed && !replacements.some((r) => r.ingredient === trimmed)) {
      setReplacements([...replacements, { ingredient: trimmed, rank: replacements.length + 1 }])
      setCurrentReplacement('')
    }
  }

  const handleRemoveReplacement = (ingredient: string) => {
    const filtered = replacements.filter((r) => r.ingredient !== ingredient)
    // Re-rank after removal
    setReplacements(filtered.map((r, idx) => ({ ...r, rank: idx + 1 })))
  }

  const handleMoveUp = (index: number) => {
    if (index === 0) return
    const newReplacements = [...replacements]
    ;[newReplacements[index], newReplacements[index - 1]] = [
      newReplacements[index - 1],
      newReplacements[index],
    ]
    // Re-rank
    setReplacements(newReplacements.map((r, idx) => ({ ...r, rank: idx + 1 })))
  }

  const handleMoveDown = (index: number) => {
    if (index === replacements.length - 1) return
    const newReplacements = [...replacements]
    ;[newReplacements[index], newReplacements[index + 1]] = [
      newReplacements[index + 1],
      newReplacements[index],
    ]
    // Re-rank
    setReplacements(newReplacements.map((r, idx) => ({ ...r, rank: idx + 1 })))
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (preference) {
      // Edit mode - only send replacements and context
      await onSave({ replacements, context: context || undefined })
    } else {
      // Create mode - send all fields
      await onSave({
        original_ingredient: originalIngredient,
        replacements,
        context: context || undefined,
      })
    }
  }

  const isValid = preference
    ? replacements.length > 0
    : originalIngredient.trim() && replacements.length > 0

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={(e) => {
        // Close modal when clicking on backdrop (not the modal content)
        if (e.target === e.currentTarget && !isSaving) {
          onClose()
        }
      }}
    >
      <div className="bg-white rounded-card max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <form onSubmit={handleSubmit} className="p-6">
          <h3 className="text-xl font-semibold text-text-primary mb-4">
            {preference ? 'Edit Substitution' : 'Add Substitution'}
          </h3>

          {/* Original ingredient (disabled in edit mode) */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-text-primary mb-2">
              Original Ingredient
            </label>
            <input
              type="text"
              value={originalIngredient}
              onChange={(e) => setOriginalIngredient(e.target.value)}
              disabled={!!preference}
              placeholder="e.g., Chicken"
              maxLength={100}
              className="w-full px-4 py-2 rounded-button border border-warm-border focus:outline-none focus:ring-2 focus:ring-olive focus:border-transparent disabled:bg-cream-dark disabled:cursor-not-allowed"
            />
          </div>

          {/* Replacements */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-text-primary mb-2">
              Replacement Ingredients (in order of preference)
            </label>
            <div className="flex gap-2 mb-3">
              <input
                type="text"
                value={currentReplacement}
                onChange={(e) => setCurrentReplacement(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    handleAddReplacement()
                  }
                }}
                placeholder="e.g., Tofu"
                maxLength={100}
                className="flex-1 px-4 py-2 rounded-button border border-warm-border focus:outline-none focus:ring-2 focus:ring-olive focus:border-transparent"
              />
              <button
                type="button"
                onClick={handleAddReplacement}
                disabled={!currentReplacement.trim()}
                className="px-4 py-2 rounded-button bg-olive text-cream font-medium hover:bg-olive-dark focus:outline-none focus:ring-2 focus:ring-olive disabled:opacity-50 transition-colors"
              >
                Add
              </button>
            </div>

            {/* Replacement list */}
            {replacements.length > 0 && (
              <div className="space-y-2">
                {replacements.map((replacement, idx) => (
                  <div
                    key={replacement.ingredient}
                    className="flex items-center gap-2 p-2 rounded-button border border-warm-border"
                  >
                    <span className="font-medium text-olive w-8">{idx + 1}.</span>
                    <span className="flex-1 text-text-primary">{replacement.ingredient}</span>
                    <div className="flex gap-1">
                      <button
                        type="button"
                        onClick={() => handleMoveUp(idx)}
                        disabled={idx === 0}
                        className="p-1 hover:bg-cream-dark rounded disabled:opacity-30"
                        aria-label="Move up"
                      >
                        ↑
                      </button>
                      <button
                        type="button"
                        onClick={() => handleMoveDown(idx)}
                        disabled={idx === replacements.length - 1}
                        className="p-1 hover:bg-cream-dark rounded disabled:opacity-30"
                        aria-label="Move down"
                      >
                        ↓
                      </button>
                      <button
                        type="button"
                        onClick={() => handleRemoveReplacement(replacement.ingredient)}
                        className="p-1 hover:bg-terra/10 text-terra rounded"
                        aria-label="Remove"
                      >
                        <X size={16} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Context (optional) */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-text-primary mb-2">
              Context (optional)
            </label>
            <input
              type="text"
              value={context}
              onChange={(e) => setContext(e.target.value)}
              placeholder="e.g., in_recipe, side_dish, protein"
              maxLength={200}
              className="w-full px-4 py-2 rounded-button border border-warm-border focus:outline-none focus:ring-2 focus:ring-olive focus:border-transparent"
            />
          </div>

          {/* Action buttons */}
          <div className="flex gap-3 justify-end">
            <button
              type="button"
              onClick={onClose}
              disabled={isSaving}
              className="px-6 py-2 rounded-button bg-cream-dark text-text-primary font-medium hover:bg-mocha/10 focus:outline-none focus:ring-2 focus:ring-mocha disabled:opacity-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!isValid || isSaving}
              className="px-6 py-2 rounded-button bg-olive text-cream font-medium hover:bg-olive-dark focus:outline-none focus:ring-2 focus:ring-olive disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isSaving ? 'Saving...' : preference ? 'Update' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
