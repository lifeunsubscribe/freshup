import type { RecipeIngredientResponse } from '../api/types'

function normalizeText(text: string): string {
  return text.toLowerCase().trim()
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

// Returns true if any significant token of the ingredient name appears as a
// whole word in the step text. "Longest first" sorting in the caller ensures
// more-specific names are matched before shorter subsets.
function ingredientMatchesStep(ingredientName: string, stepText: string): boolean {
  const normalizedName = normalizeText(ingredientName)
  const normalizedStep = normalizeText(stepText)

  const tokens = normalizedName
    .split(/[\s\-_/]+/)
    .filter(t => t.length > 2)

  if (tokens.length === 0) return false

  return tokens.some(token => {
    const re = new RegExp(`\\b${escapeRegex(token)}\\b`)
    return re.test(normalizedStep)
  })
}

/**
 * Returns the ingredients that belong to a given step.
 *
 * Mode selection (recipe-level, not per-step):
 *   - If any ingredient in the recipe has step_index set, use step_index for
 *     all steps and skip name matching. This covers manually authored recipes.
 *   - Otherwise (all step_index === null, typical for imported recipes), match
 *     by name: an ingredient matches the step if any of its tokens appears as a
 *     whole word in the step text. Ingredients are tested longest-first to give
 *     more specific names priority; results are returned in recipe order.
 */
export function ingredientsForStep(
  stepIndex: number,
  step: string,
  ingredients: RecipeIngredientResponse[]
): RecipeIngredientResponse[] {
  const hasStepIndex = ingredients.some(ing => ing.step_index !== null)
  if (hasStepIndex) {
    return ingredients.filter(ing => ing.step_index === stepIndex)
  }

  // Name-matching: sort by name length descending for priority, then
  // filter, then restore original recipe order.
  const byLength = [...ingredients].sort(
    (a, b) => b.ingredient_name.length - a.ingredient_name.length
  )
  const matched = new Set(byLength.filter(ing => ingredientMatchesStep(ing.ingredient_name, step)))
  return ingredients.filter(ing => matched.has(ing))
}
