import { useState, useRef, useEffect } from 'react'
import Sheet from '../ui/Sheet'
import { useCreateGroceryItem, useGroceryList } from '../../api/hooks/useGrocery'
import { batchPromises } from '../../utils/batchPromises'
import { isUnparseableQuantity } from '../../constants/recipe'
import type { PantryCheckResult, IngredientStockStatus } from '../../utils/pantryMatcher'
import type { RecipeIngredientResponse } from '../../api/types'

function formatQuantity(quantity: number, multiplier: number = 1): string {
  if (isUnparseableQuantity(quantity, multiplier)) {
    return ''
  }
  if (Math.abs(quantity - Math.round(quantity)) < 0.001) {
    return Math.round(quantity).toString()
  }
  const fractions = [
    { decimal: 1 / 3, display: '1/3' },
    { decimal: 2 / 3, display: '2/3' },
    { decimal: 1 / 4, display: '1/4' },
    { decimal: 3 / 4, display: '3/4' },
    { decimal: 1 / 2, display: '1/2' },
    { decimal: 1 / 8, display: '1/8' },
    { decimal: 3 / 8, display: '3/8' },
    { decimal: 5 / 8, display: '5/8' },
    { decimal: 7 / 8, display: '7/8' },
  ]
  const TOLERANCE = 0.01
  const wholePart = Math.floor(quantity)
  const fractionalPart = quantity - wholePart
  for (const fraction of fractions) {
    if (Math.abs(fractionalPart - fraction.decimal) < TOLERANCE) {
      return wholePart > 0 ? `${wholePart} ${fraction.display}` : fraction.display
    }
  }
  return quantity.toFixed(2)
}

interface PantryReviewSheetProps {
  open: boolean
  onClose: () => void
  ingredients: RecipeIngredientResponse[]
  stockStatus: PantryCheckResult
  servingsMultiplier: number
  onSuccess: (count: number) => void
}

interface OrderedRow {
  status: IngredientStockStatus
  isOptional: boolean
}

export default function PantryReviewSheet({
  open,
  onClose,
  ingredients,
  stockStatus,
  servingsMultiplier,
  onSuccess,
}: PantryReviewSheetProps) {
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set())
  const [failedIds, setFailedIds] = useState<Set<string>>(new Set())
  const [isSubmitting, setIsSubmitting] = useState(false)
  const addedItemsRef = useRef<Set<string>>(new Set())

  const createGroceryItem = useCreateGroceryItem()
  const { data: existingGroceryItems = [], refetch: refetchGroceryList } = useGroceryList({ purchased: false })

  // Build an id→status lookup from stockStatus
  const statusMap = new Map<string, IngredientStockStatus>()
  stockStatus.inStock.forEach(s => statusMap.set(s.ingredient.id, s))
  stockStatus.outOfStock.forEach(s => statusMap.set(s.ingredient.id, s))
  const inStockIds = new Set(stockStatus.inStock.map(s => s.ingredient.id))

  // Build the display order: required in recipe order, then optional
  const required: OrderedRow[] = []
  const optional: OrderedRow[] = []
  for (const ing of ingredients) {
    const status = statusMap.get(ing.id)
    if (!status) continue
    if (ing.is_optional) optional.push({ status, isOptional: true })
    else required.push({ status, isOptional: false })
  }
  const ordered: OrderedRow[] = [...required, ...optional]

  // Reset per-open state when the sheet becomes visible
  useEffect(() => {
    if (!open) return
    const nextChecked = new Set<string>()
    for (const row of ordered) {
      if (!inStockIds.has(row.status.ingredient.id)) {
        nextChecked.add(row.status.ingredient.id)
      }
    }
    setCheckedIds(nextChecked)
    setFailedIds(new Set())
    addedItemsRef.current = new Set()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]) // intentional: only reset on open/close, not on every stockStatus change

  const toggleCheck = (id: string) => {
    setCheckedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const checkedCount = checkedIds.size
  const failedCount = failedIds.size
  const hasFailures = failedCount > 0

  const handleSubmit = async () => {
    if (checkedCount === 0 || isSubmitting) return
    setIsSubmitting(true)

    try {
      const { data: latestItems } = await refetchGroceryList()
      const currentItems = latestItems || existingGroceryItems
      const existingNames = new Set(currentItems.map(i => i.item_name.toLowerCase()))

      const rowsToAdd = ordered.filter(row => {
        if (!checkedIds.has(row.status.ingredient.id)) return false
        const nameLower = row.status.ingredient.ingredient_name.toLowerCase()
        return !existingNames.has(nameLower) && !addedItemsRef.current.has(nameLower)
      })

      const skippedCount = checkedCount - rowsToAdd.length

      if (rowsToAdd.length === 0) {
        onSuccess(skippedCount > 0 ? checkedCount : 0)
        onClose()
        return
      }

      const promiseFns = rowsToAdd.map(({ status }) => () => {
        const { ingredient } = status
        const rawQty = ingredient.quantity
        const scaledQty = isUnparseableQuantity(rawQty, 1) ? rawQty : rawQty * servingsMultiplier
        return createGroceryItem.mutateAsync({
          item_name: ingredient.ingredient_name,
          quantity: scaledQty,
          unit: ingredient.unit,
          source: 'recipe',
        })
      })

      const results = await batchPromises(promiseFns, 5)

      const newFailedIds = new Set<string>()
      let successCount = 0

      results.forEach((result, idx) => {
        const ing = rowsToAdd[idx].status.ingredient
        if (result.status === 'fulfilled') {
          addedItemsRef.current.add(ing.ingredient_name.toLowerCase())
          successCount++
        } else {
          newFailedIds.add(ing.id)
        }
      })

      if (newFailedIds.size === 0) {
        onSuccess(successCount + skippedCount)
        onClose()
      } else {
        setFailedIds(newFailedIds)
      }
    } catch (err) {
      console.error('Failed to add ingredients.', err)
      setFailedIds(new Set(checkedIds))
    } finally {
      setIsSubmitting(false)
    }
  }

  const footerButtonLabel = hasFailures
    ? `Retry ${failedCount}`
    : `Add ${checkedCount} to the grocery list`

  const footer = (
    <div className="px-4 py-3">
      <button
        onClick={handleSubmit}
        disabled={checkedCount === 0 || isSubmitting}
        className="w-full bg-olive text-cream font-medium py-3 px-4 rounded-button hover:bg-olive-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isSubmitting ? 'Adding…' : footerButtonLabel}
      </button>
    </div>
  )

  return (
    <Sheet open={open} onClose={onClose} title="Pantry review" footer={footer}>
      <div className="px-4 pb-2">
        {ordered.map((row) => {
          const { ingredient } = row.status
          const id = ingredient.id
          const checked = checkedIds.has(id)
          const failed = failedIds.has(id)
          const scaledQty = ingredient.quantity * servingsMultiplier
          const formattedQty = formatQuantity(scaledQty, servingsMultiplier)
          const amountText = formattedQty
            ? `${formattedQty} ${ingredient.unit}`.trim()
            : ingredient.unit || ''
          const label = inStockIds.has(id) ? 'In the pantry' : 'Needed'

          return (
            <label
              key={id}
              className={`flex items-start gap-3 py-3 border-b border-warm-border last:border-b-0 cursor-pointer ${failed ? 'text-mocha' : ''}`}
            >
              <input
                type="checkbox"
                checked={checked}
                onChange={() => toggleCheck(id)}
                className="mt-0.5 h-4 w-4 rounded border-warm-border text-olive focus:ring-olive flex-shrink-0"
              />
              <div className="flex-1 min-w-0">
                <span className="text-sm text-text-primary">
                  {ingredient.ingredient_name}
                  {row.isOptional && (
                    <span className="ml-1 text-text-secondary">(optional)</span>
                  )}
                </span>
                {amountText && (
                  <span className="ml-2 text-sm text-text-secondary">{amountText}</span>
                )}
              </div>
              <span className={`text-xs flex-shrink-0 ${failed ? 'text-mocha font-medium' : 'text-text-secondary'}`}>
                {failed ? 'Failed' : label}
              </span>
            </label>
          )
        })}
      </div>
    </Sheet>
  )
}
