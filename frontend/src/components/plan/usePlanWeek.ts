import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  useWeekPlan,
  useGenerateDraft,
  useConfirmEntry,
  useSwapEntry,
  useOpenCard,
} from '../../api'
import type { MealPlanEntryDisplay } from '../../api/types'
import { weekDates } from '../../utils/week'

export interface PlanDay {
  date: string
  entry: MealPlanEntryDisplay | undefined
}

export interface PlanStats {
  /** Accepted dinners. */
  planned: number
  /** Suggestions not yet accepted. */
  suggested: number
  /** Cooking time over the dinners that state one, in minutes. */
  minutes: number
}

/**
 * One week of the meal plan and everything that can be done to it with the
 * endpoints that exist: fill an empty week with suggestions, accept one or all,
 * swap one, open a dinner's recipe. Shared by the plan card on the Plan page
 * and the week editor.
 */
export function usePlanWeek(weekStart: string, { autoFill }: { autoFill: boolean }) {
  const navigate = useNavigate()
  const { data: week, isLoading, isError, refetch } = useWeekPlan(weekStart)
  const generate = useGenerateDraft()
  const confirm = useConfirmEntry()
  const swap = useSwapEntry()
  const openCard = useOpenCard()

  // What the last accept did, shown once near the week's header.
  const [notice, setNotice] = useState<string | null>(null)
  // The entry whose accept, swap or open failed, and why.
  const [rowError, setRowError] = useState<{ entryId: string; message: string } | null>(null)
  const [acceptingAll, setAcceptingAll] = useState(false)

  const isEmpty =
    week !== undefined && week.confirmed_entries.length === 0 && week.draft_entries.length === 0

  // An empty week starts filled with suggestions. Once per week per visit, so a
  // failed or empty generation does not loop; suggest() retries by hand.
  // The ref is the guard (it holds under StrictMode's double effect); the state
  // copy is what callers read to know the automatic attempt has started.
  const autoFilled = useRef(new Set<string>())
  const [attemptedWeeks, setAttemptedWeeks] = useState<string[]>([])
  const generateDraft = generate.mutate
  useEffect(() => {
    if (!autoFill || !isEmpty || autoFilled.current.has(weekStart)) return
    autoFilled.current.add(weekStart)
    setAttemptedWeeks((weeks) => [...weeks, weekStart])
    generateDraft(weekStart)
  }, [autoFill, isEmpty, weekStart, generateDraft])

  // Confirmed takes precedence over a draft on the same day.
  const entryByDate = new Map<string, MealPlanEntryDisplay>()
  if (week) {
    for (const e of week.draft_entries) entryByDate.set(e.date, e)
    for (const e of week.confirmed_entries) entryByDate.set(e.date, e)
  }
  const days: PlanDay[] = weekDates(weekStart).map((date) => ({ date, entry: entryByDate.get(date) }))
  const shown = days.flatMap((day) => (day.entry ? [day.entry] : []))
  const suggestions = shown.filter((e) => e.status === 'draft')
  const stats: PlanStats = {
    planned: shown.length - suggestions.length,
    suggested: suggestions.length,
    minutes: shown.reduce((sum, e) => sum + (e.display?.prep_time_minutes ?? 0), 0),
  }

  function failure(entryId: string, fallback: string) {
    return (error: unknown) => {
      const message = error instanceof Error && error.message ? error.message : fallback
      setRowError({ entryId, message })
    }
  }

  function groceryNotice(prefix: string, added: number): string {
    if (added === 0) return `${prefix} Nothing new was needed on your grocery list.`
    return `${prefix} Added ${added} ${added === 1 ? 'item' : 'items'} to your grocery list.`
  }

  function accept(entry: MealPlanEntryDisplay) {
    setNotice(null)
    setRowError(null)
    confirm.mutate(entry.id, {
      onSuccess: (result) => setNotice(groceryNotice('Accepted.', result.grocery_items_added)),
      onError: failure(entry.id, 'Could not accept this one. Try again.'),
    })
  }

  /** Accept every suggestion in the week, one at a time (each may import a recipe). */
  async function acceptAll() {
    setNotice(null)
    setRowError(null)
    setAcceptingAll(true)
    let accepted = 0
    let added = 0
    for (const entry of suggestions) {
      try {
        const result = await confirm.mutateAsync(entry.id)
        accepted += 1
        added += result.grocery_items_added
      } catch (error) {
        failure(entry.id, 'Could not accept this one. Try again.')(error)
        break
      }
    }
    setAcceptingAll(false)
    if (accepted > 0) {
      setNotice(
        groceryNotice(`Accepted ${accepted} ${accepted === 1 ? 'dinner' : 'dinners'}.`, added)
      )
    }
  }

  function swapEntry(entry: MealPlanEntryDisplay) {
    setNotice(null)
    setRowError(null)
    swap.mutate(entry.id, {
      onError: failure(entry.id, 'Nothing else to suggest for this day right now.'),
    })
  }

  function open(entry: MealPlanEntryDisplay) {
    if (entry.recipe_id) {
      navigate(`/recipes/${entry.recipe_id}`)
      return
    }
    if (entry.catalog_card_id) {
      setRowError(null)
      openCard.mutate(
        {
          cardId: entry.catalog_card_id,
          source: entry.display?.source_type ?? '',
          collectionSlug: '',
        },
        {
          onSuccess: (recipe) => navigate(`/recipes/${recipe.id}`),
          onError: failure(entry.id, 'Could not open this recipe. Try again.'),
        }
      )
    }
  }

  const busyEntryId = confirm.isPending
    ? confirm.variables
    : swap.isPending
      ? swap.variables
      : undefined

  return {
    isLoading,
    isError,
    retryLoad: () => void refetch(),
    isEmpty,
    days,
    stats,
    notice,
    /** The error to show on this entry, if its last action failed. */
    errorFor: (entry: MealPlanEntryDisplay | undefined) =>
      entry && rowError?.entryId === entry.id ? rowError.message : null,
    /** True while this entry is being accepted or swapped, or all are being accepted. */
    isBusy: (entry: MealPlanEntryDisplay | undefined) =>
      acceptingAll || (entry !== undefined && entry.id === busyEntryId),
    acceptingAll,
    accept,
    acceptAll: () => void acceptAll(),
    swap: swapEntry,
    open,
    suggesting: generate.isPending,
    suggestFailed: generate.isError,
    /** The automatic fill has started (or was never due), so "nothing planned" can be said. */
    autoFillStarted: !autoFill || attemptedWeeks.includes(weekStart),
    suggest: () => generate.mutate(weekStart),
  }
}

export type PlanWeekState = ReturnType<typeof usePlanWeek>
