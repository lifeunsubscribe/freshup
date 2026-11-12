import { useState } from 'react'
import Sheet from '../ui/Sheet'
import type { MealType } from '../../api/types'

const MEAL_TYPES: { value: MealType; label: string }[] = [
  { value: 'breakfast', label: 'Breakfast' },
  { value: 'lunch', label: 'Lunch' },
  { value: 'dinner', label: 'Dinner' },
  { value: 'snack', label: 'Snack' },
]

function buildDayOptions(): { label: string; value: string }[] {
  const days: { label: string; value: string }[] = []
  const today = new Date()
  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

  for (let i = 0; i < 7; i++) {
    const d = new Date(today)
    d.setDate(today.getDate() + i)
    const iso = d.toISOString().slice(0, 10)
    const label = i === 0 ? 'Today' : dayNames[d.getDay()]
    days.push({ label, value: iso })
  }
  return days
}

interface AddToPlanSheetProps {
  open: boolean
  onClose: () => void
  recipeId: string
  defaultServings: number
  onAdd: (date: string, mealType: MealType, servings: number) => Promise<void>
}

export default function AddToPlanSheet({
  open,
  onClose,
  recipeId: _recipeId,
  defaultServings,
  onAdd,
}: AddToPlanSheetProps) {
  const dayOptions = buildDayOptions()
  const [selectedDate, setSelectedDate] = useState(dayOptions[0].value)
  const [selectedMeal, setSelectedMeal] = useState<MealType>('dinner')
  const [servings, setServings] = useState(defaultServings)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleAdd = async () => {
    setIsSubmitting(true)
    setError(null)
    try {
      await onAdd(selectedDate, selectedMeal, servings)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to add to plan. Please try again.'
      setError(msg)
    } finally {
      setIsSubmitting(false)
    }
  }

  const chipBase = 'px-3 py-2 rounded-button text-sm font-medium transition-colors border'
  const chipSelected = 'bg-olive text-cream border-olive'
  const chipUnselected = 'bg-cream text-text-primary border-warm-border hover:bg-cream-dark'

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Add to plan"
      footer={
        <div className="px-4 py-3">
          {error && (
            <p className="text-sm text-mocha mb-2">{error}</p>
          )}
          <button
            onClick={handleAdd}
            disabled={isSubmitting}
            className="w-full bg-olive text-cream font-medium py-3 rounded-button hover:bg-olive-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSubmitting ? 'Adding…' : 'Add'}
          </button>
        </div>
      }
    >
      <div className="px-4 pt-2 pb-4 space-y-5">
        {/* Day selector */}
        <div>
          <p className="text-xs font-medium text-text-secondary uppercase tracking-wide mb-2">Day</p>
          <div className="flex gap-2 overflow-x-auto pb-1">
            {dayOptions.map((day) => (
              <button
                key={day.value}
                onClick={() => setSelectedDate(day.value)}
                className={`${chipBase} flex-shrink-0 ${selectedDate === day.value ? chipSelected : chipUnselected}`}
                aria-pressed={selectedDate === day.value}
              >
                {day.label}
              </button>
            ))}
          </div>
        </div>

        {/* Meal type selector */}
        <div>
          <p className="text-xs font-medium text-text-secondary uppercase tracking-wide mb-2">Meal</p>
          <div className="flex gap-2 flex-wrap">
            {MEAL_TYPES.map((meal) => (
              <button
                key={meal.value}
                onClick={() => setSelectedMeal(meal.value)}
                className={`${chipBase} ${selectedMeal === meal.value ? chipSelected : chipUnselected}`}
                aria-pressed={selectedMeal === meal.value}
              >
                {meal.label}
              </button>
            ))}
          </div>
        </div>

        {/* Servings */}
        <div>
          <p className="text-xs font-medium text-text-secondary uppercase tracking-wide mb-2">Servings</p>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setServings((s) => Math.max(1, s - 1))}
              className="w-9 h-9 rounded-full border border-warm-border bg-cream flex items-center justify-center text-text-primary hover:bg-cream-dark transition-colors"
              aria-label="Decrease servings"
            >
              −
            </button>
            <span className="text-lg font-medium text-text-primary w-6 text-center">{servings}</span>
            <button
              onClick={() => setServings((s) => s + 1)}
              className="w-9 h-9 rounded-full border border-warm-border bg-cream flex items-center justify-center text-text-primary hover:bg-cream-dark transition-colors"
              aria-label="Increase servings"
            >
              +
            </button>
          </div>
        </div>
      </div>
    </Sheet>
  )
}
