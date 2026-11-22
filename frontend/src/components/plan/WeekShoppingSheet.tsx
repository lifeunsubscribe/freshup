import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Sheet from '../ui/Sheet'
import { useAddWeekShopping, useWeekShopping } from '../../api'
import type { ShoppingLine } from '../../api/types'
import { formatAmount } from '../../utils/amount'

interface WeekShoppingSheetProps {
  open: boolean
  onClose: () => void
  weekStart: string
  /** "this week", "next week": how the sheet names the week. */
  weekName: string
}

/** What the line says about pantry and list, if anything. */
function lineNote(line: ShoppingLine): string | null {
  if (line.listed_otherwise) return 'Already on your grocery list'
  if (line.listed_quantity > 0 && line.add_quantity <= 0) return 'Already on your grocery list'
  if (line.pantry_quantity !== null && line.pantry_unit !== null) {
    const have = `You have ${formatAmount(line.pantry_quantity, line.pantry_unit, false)}`
    if (line.pantry_counted) return line.add_quantity > 0 ? `${have}, counted` : `${have}, enough`
    return `${have}; check whether it is enough`
  }
  return null
}

/**
 * The week's shopping list as a checklist: every ingredient the accepted
 * dinners need, merged across recipes, checked against the pantry and the
 * grocery list. Lines start checked when they look needed; the user adjusts
 * and adds what is checked.
 */
export default function WeekShoppingSheet({ open, onClose, weekStart, weekName }: WeekShoppingSheetProps) {
  const { data, isLoading, isError, refetch } = useWeekShopping(weekStart, { enabled: open })
  const add = useAddWeekShopping()
  const [checked, setChecked] = useState<Set<string>>(new Set())
  const [result, setResult] = useState<{ added: number; skipped: string[] } | null>(null)
  const reset = add.reset

  // Each opening starts from the suggestions of the moment.
  useEffect(() => {
    if (!open) {
      setResult(null)
      reset()
      return
    }
    if (data) setChecked(new Set(data.lines.filter((l) => l.suggested).map((l) => l.key)))
  }, [open, data, reset])

  // A line can be added only when it would put something on the list.
  const addable = (line: ShoppingLine) => line.to_taste || line.add_quantity > 0

  function toggle(key: string) {
    setChecked((current) => {
      const next = new Set(current)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const chosen = data ? data.lines.filter((l) => checked.has(l.key) && addable(l)).map((l) => l.key) : []

  function handleAdd() {
    add.mutate(
      { weekStart, keys: chosen },
      { onSuccess: (response) => setResult(response) }
    )
  }

  const footer = result ? (
    <button onClick={onClose} className="w-full h-11 rounded-button bg-olive text-white text-[15px] font-medium">
      Done
    </button>
  ) : (
    <button
      onClick={handleAdd}
      disabled={chosen.length === 0 || add.isPending}
      className="w-full h-11 rounded-button bg-olive text-white text-[15px] font-medium disabled:opacity-50"
    >
      {add.isPending
        ? 'Adding...'
        : `Add ${chosen.length} ${chosen.length === 1 ? 'item' : 'items'} to grocery list`}
    </button>
  )

  return (
    <Sheet open={open} onClose={onClose} title={`Shopping for ${weekName}`} footer={data?.lines.length ? footer : undefined}>
      <div className="px-4 pt-2 pb-4">
        {isLoading && <p className="text-sm text-text-secondary">Working out what you need...</p>}
        {isError && (
          <p className="text-sm text-text-secondary">
            Could not work out the list.{' '}
            <button onClick={() => refetch()} className="text-olive underline">
              Try again
            </button>
          </p>
        )}

        {result && (
          <div role="status" className="space-y-2 text-[14px] text-text-primary">
            <p>
              Added {result.added} {result.added === 1 ? 'item' : 'items'} to your grocery list.{' '}
              <Link to="/grocery" onClick={onClose} className="text-olive underline">
                Open the list
              </Link>
            </p>
            {result.skipped.length > 0 && (
              <p className="text-[13px] text-text-secondary">Could not add: {result.skipped.join(', ')}.</p>
            )}
          </div>
        )}

        {!result && data && data.dinners === 0 && (
          <p className="text-sm text-text-secondary">
            Accept a dinner or two first. The list is worked out from the dinners you have accepted.
          </p>
        )}

        {!result && data && data.dinners > 0 && (
          <>
            <p className="text-[13px] text-text-secondary mb-3">
              From {data.dinners} accepted {data.dinners === 1 ? 'dinner' : 'dinners'}, with what is in your pantry
              and already on your list taken off. Uncheck anything you do not need.
            </p>
            <ul className="divide-y divide-warm-border" aria-label="Ingredients for the week">
              {data.lines.map((line) => {
                const note = lineNote(line)
                const can = addable(line)
                const amount = formatAmount(
                  can ? line.add_quantity : line.quantity,
                  line.unit,
                  line.to_taste
                )
                return (
                  <li key={line.key}>
                    <label className={`flex items-start gap-3 py-2.5 min-h-[44px] ${can ? '' : 'opacity-60'}`}>
                      <input
                        type="checkbox"
                        checked={can && checked.has(line.key)}
                        disabled={!can}
                        onChange={() => toggle(line.key)}
                        className="mt-1 h-[18px] w-[18px] accent-olive"
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block text-[15px] text-text-primary">
                          {line.name} <span className="text-text-secondary">({amount})</span>
                        </span>
                        <span className="block text-[12px] text-text-secondary">
                          For {line.needs.map((n) => n.recipe_name).join(', ')}
                        </span>
                        {note && <span className="block text-[12px] text-olive-dark">{note}</span>}
                      </span>
                    </label>
                  </li>
                )
              })}
            </ul>
            {add.isError && (
              <p role="alert" className="mt-3 text-[13px] text-terra-dark">
                Could not add those. Try again.
              </p>
            )}
          </>
        )}
      </div>
    </Sheet>
  )
}
