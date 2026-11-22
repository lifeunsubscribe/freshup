import { useEffect, useRef, useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import Sheet from '../ui/Sheet'
import { useSaveVariation } from '../../api/hooks/useRecipes'
import type { RecipeResponse, VariationIngredient } from '../../api/types'
import { isToTaste } from '../../utils/amount'

interface VariationSheetProps {
  open: boolean
  onClose: () => void
  recipe: RecipeResponse
  /** True when the recipe already is this user's version: saving updates it. */
  isOwnVersion: boolean
  onSaved: (version: RecipeResponse, created: boolean) => void
}

/** An ingredient row as typed: amounts are text until saved. */
interface DraftIngredient {
  key: number
  name: string
  amount: string
  unit: string
}

let nextKey = 0

function toDraft(recipe: RecipeResponse): { name: string; ingredients: DraftIngredient[]; steps: string } {
  return {
    name: recipe.name,
    ingredients: recipe.ingredients.map((i) => ({
      key: nextKey++,
      name: i.ingredient_name,
      amount: isToTaste(i.quantity) ? '' : String(i.quantity),
      unit: i.unit,
    })),
    steps: recipe.steps.join('\n\n'),
  }
}

/**
 * Change a recipe's ingredients and steps. Saving never changes the original:
 * it saves the user's own version, listed under My variations on My recipes.
 */
export default function VariationSheet({ open, onClose, recipe, isOwnVersion, onSaved }: VariationSheetProps) {
  const save = useSaveVariation()
  const [draft, setDraft] = useState(() => toDraft(recipe))
  const [problem, setProblem] = useState<string | null>(null)
  const reset = save.reset

  // Start from the recipe each time the sheet opens, and only then: a
  // re-render while open must not throw away what the user has typed.
  const wasOpen = useRef(false)
  useEffect(() => {
    if (open && !wasOpen.current) {
      setDraft(toDraft(recipe))
      setProblem(null)
      reset()
    }
    wasOpen.current = open
  }, [open, recipe, reset])

  function updateIngredient(key: number, field: 'name' | 'amount' | 'unit', value: string) {
    setDraft((d) => ({
      ...d,
      ingredients: d.ingredients.map((i) => (i.key === key ? { ...i, [field]: value } : i)),
    }))
  }

  function handleSave() {
    const ingredients: VariationIngredient[] = []
    for (const row of draft.ingredients) {
      const name = row.name.trim()
      if (!name) continue
      const amountText = row.amount.trim()
      // An empty amount is "to taste", stored the way the importer stores it.
      const quantity = amountText === '' ? 0.001 : Number(amountText.replace(',', '.'))
      if (!Number.isFinite(quantity) || quantity <= 0) {
        setProblem(`"${row.amount}" is not an amount for ${name}. Use a number, or leave it empty for "to taste".`)
        return
      }
      ingredients.push({ ingredient_name: name, quantity, unit: row.unit.trim() })
    }
    if (ingredients.length === 0) {
      setProblem('A recipe needs at least one ingredient.')
      return
    }
    setProblem(null)
    const steps = draft.steps
      .split(/\n\s*\n/)
      .map((s) => s.trim())
      .filter(Boolean)
    const name = draft.name.trim()
    save.mutate(
      {
        recipeId: recipe.id,
        changes: { ingredients, steps, ...(isOwnVersion && name ? { name } : {}) },
      },
      { onSuccess: (version) => onSaved(version, version.id !== recipe.id) }
    )
  }

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title={isOwnVersion ? 'Edit your version' : 'Make it your own'}
      footer={
        <button
          onClick={handleSave}
          disabled={save.isPending}
          className="w-full h-11 rounded-button bg-olive text-white text-[15px] font-medium disabled:opacity-50"
        >
          {save.isPending ? 'Saving...' : isOwnVersion ? 'Save changes' : 'Save as my version'}
        </button>
      }
    >
      <div className="px-4 pt-2 pb-4 space-y-5">
        <p className="text-[13px] text-text-secondary">
          {isOwnVersion
            ? 'This is your version. Changes save to it.'
            : 'The original stays as it is. Your changes are saved as your own version, under My variations in My recipes.'}
        </p>

        {isOwnVersion && (
          <div>
            <label htmlFor="variation-name" className="block text-xs font-medium text-text-secondary uppercase tracking-wide mb-1.5">
              Name
            </label>
            <input
              id="variation-name"
              value={draft.name}
              onChange={(e) => setDraft((d) => ({ ...d, name: e.target.value }))}
              maxLength={255}
              className="w-full h-10 rounded-input border border-warm-border bg-white px-3 text-[14px]"
            />
          </div>
        )}

        <fieldset>
          <legend className="text-xs font-medium text-text-secondary uppercase tracking-wide mb-2">Ingredients</legend>
          <ul className="space-y-2">
            {draft.ingredients.map((row, index) => (
              <li key={row.key} className="flex items-center gap-2">
                <input
                  aria-label={`Amount for ingredient ${index + 1}`}
                  value={row.amount}
                  onChange={(e) => updateIngredient(row.key, 'amount', e.target.value)}
                  placeholder="to taste"
                  inputMode="decimal"
                  className="w-16 h-10 rounded-input border border-warm-border bg-white px-2 text-[14px]"
                />
                <input
                  aria-label={`Unit for ingredient ${index + 1}`}
                  value={row.unit}
                  onChange={(e) => updateIngredient(row.key, 'unit', e.target.value)}
                  placeholder="unit"
                  maxLength={50}
                  className="w-20 h-10 rounded-input border border-warm-border bg-white px-2 text-[14px]"
                />
                <input
                  aria-label={`Ingredient ${index + 1}`}
                  value={row.name}
                  onChange={(e) => updateIngredient(row.key, 'name', e.target.value)}
                  placeholder="Ingredient"
                  maxLength={255}
                  className="flex-1 min-w-0 h-10 rounded-input border border-warm-border bg-white px-2 text-[14px]"
                />
                <button
                  type="button"
                  onClick={() =>
                    setDraft((d) => ({ ...d, ingredients: d.ingredients.filter((i) => i.key !== row.key) }))
                  }
                  aria-label={`Remove ${row.name || `ingredient ${index + 1}`}`}
                  className="flex items-center justify-center w-9 h-9 flex-shrink-0 rounded-button-sm border border-warm-btn-border text-text-secondary"
                >
                  <Trash2 size={14} />
                </button>
              </li>
            ))}
          </ul>
          <button
            type="button"
            onClick={() =>
              setDraft((d) => ({
                ...d,
                ingredients: [...d.ingredients, { key: nextKey++, name: '', amount: '', unit: '' }],
              }))
            }
            className="mt-2 flex items-center gap-1 text-[13px] text-olive"
          >
            <Plus size={14} />
            Add an ingredient
          </button>
        </fieldset>

        <div>
          <label htmlFor="variation-steps" className="block text-xs font-medium text-text-secondary uppercase tracking-wide mb-1.5">
            Steps
          </label>
          <p className="text-[12px] text-text-tertiary mb-1.5">Leave a blank line between steps.</p>
          <textarea
            id="variation-steps"
            value={draft.steps}
            onChange={(e) => setDraft((d) => ({ ...d, steps: e.target.value }))}
            rows={10}
            className="w-full rounded-input border border-warm-border bg-white p-3 text-[14px]"
          />
        </div>

        {(problem || save.isError) && (
          <p role="alert" className="text-[13px] text-terra-dark">
            {problem ?? 'Could not save your version. Try again.'}
          </p>
        )}
      </div>
    </Sheet>
  )
}
