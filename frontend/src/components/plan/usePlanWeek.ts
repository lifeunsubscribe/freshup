import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  useWeekPlan,
  useGenerateDraft,
  useConfirmEntry,
  useSwapEntry,
  useOpenCard,
  useCreatePlanEntry,
  useRemixWeek,
  useRemovePlanEntry,
} from '../../api'
import type { DinnerPick } from './AddDinnerBand'
import type { MealPlanEntryDisplay } from '../../api/types'
import { todayStr, weekDates } from '../../utils/week'

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
  const create = useCreatePlanEntry()
  const remixWeek = useRemixWeek()
  const removeEntry = useRemovePlanEntry()

  // What the last accept did, shown once near the week's header.
  const [notice, setNotice] = useState<string | null>(null)
  // The entry whose accept, swap or open failed, and why.
  const [rowError, setRowError] = useState<{ entryId: string; message: string } | null>(null)
  const [acceptingAll, setAcceptingAll] = useState(false)
  // Adding a dinner by hand: which day is in flight, and why the last try failed.
  const [addingDate, setAddingDate] = useState<string | null>(null)
  const [addError, setAddError] = useState<string | null>(null)

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
  // Days still to come (today included) that hold nothing, in a week that is
  // otherwise under way. An entirely empty week is handled by the automatic fill.
  const today = todayStr()
  const openDays = isEmpty ? 0 : days.filter((day) => !day.entry && day.date >= today).length
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

  function accept(entry: MealPlanEntryDisplay) {
    setNotice(null)
    setRowError(null)
    confirm.mutate(entry.id, {
      onSuccess: () => setNotice('Accepted.'),
      onError: failure(entry.id, 'Could not accept this one. Try again.'),
    })
  }

  /** Accept every suggestion in the week, one at a time (each may import a recipe). */
  async function acceptAll() {
    setNotice(null)
    setRowError(null)
    setAcceptingAll(true)
    let accepted = 0
    for (const entry of suggestions) {
      try {
        await confirm.mutateAsync(entry.id)
        accepted += 1
      } catch (error) {
        failure(entry.id, 'Could not accept this one. Try again.')(error)
        break
      }
    }
    setAcceptingAll(false)
    if (accepted > 0) {
      setNotice(`Accepted ${accepted} ${accepted === 1 ? 'dinner' : 'dinners'}.`)
    }
  }

  /**
   * Put a chosen dinner on a day and accept it. Resolves true once the dinner
   * is on the day. If only the accept fails (a catalog recipe that could not
   * be fetched), the dinner stays on the day as a suggestion with the reason.
   */
  async function add(date: string, pick: DinnerPick): Promise<boolean> {
    setNotice(null)
    setRowError(null)
    setAddError(null)
    setAddingDate(date)
    try {
      const entry = await create.mutateAsync({
        date,
        meal_type: 'dinner',
        ...('recipeId' in pick ? { recipe_id: pick.recipeId } : { catalog_card_id: pick.cardId }),
      })
      try {
        await confirm.mutateAsync(entry.id)
        setNotice('Added.')
      } catch (error) {
        failure(entry.id, 'Added as a suggestion. Could not accept it yet.')(error)
        void refetch()
      }
      return true
    } catch (error) {
      setAddError(
        error instanceof Error && error.message ? error.message : 'Could not add this one. Try again.'
      )
      return false
    } finally {
      setAddingDate(null)
    }
  }

  /**
   * Draw a fresh set of suggestions for the week. Accepted dinners stay, and so
   * do suggestions on days already past.
   */
  function remix() {
    setNotice(null)
    setRowError(null)
    remixWeek.mutate(
      { weekStart, fromDate: today },
      {
        onSuccess: (result) => {
          if (result.changed === 0) setNotice('Nothing else to suggest for this week right now.')
        },
        onError: () => setNotice('Could not remix this week. Try again.'),
      }
    )
  }

  /** Take a dinner off the plan; its unpurchased grocery items go with it. */
  function remove(entry: MealPlanEntryDisplay) {
    setNotice(null)
    setRowError(null)
    removeEntry.mutate(entry.id, {
      onSuccess: (result) => {
        const gone = result.grocery_items_removed
        setNotice(
          gone > 0
            ? `Removed. Took ${gone} ${gone === 1 ? 'item' : 'items'} off your grocery list.`
            : 'Removed.'
        )
      },
      onError: failure(entry.id, 'Could not remove this one. Try again.'),
    })
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
      : removeEntry.isPending
        ? removeEntry.variables
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
      acceptingAll || remixWeek.isPending || (entry !== undefined && entry.id === busyEntryId),
    remix,
    remixing: remixWeek.isPending,
    /** Suggestions a remix would redraw: those from today on. */
    remixable: suggestions.filter((e) => e.date >= today).length,
    acceptingAll,
    accept,
    acceptAll: () => void acceptAll(),
    swap: swapEntry,
    remove,
    open,
    add,
    addingDate,
    addError,
    clearAddError: () => setAddError(null),
    /** What the week already holds, so the add band does not offer it again. */
    taken: {
      recipeIds: new Set(shown.flatMap((e) => (e.recipe_id ? [e.recipe_id] : []))),
      cardIds: new Set(shown.flatMap((e) => (e.catalog_card_id ? [e.catalog_card_id] : []))),
    },
    suggesting: generate.isPending,
    suggestFailed: generate.isError,
    /** The automatic fill has started (or was never due), so "nothing planned" can be said. */
    autoFillStarted: !autoFill || attemptedWeeks.includes(weekStart),
    suggest: () => generate.mutate(weekStart),
    openDays,
    /** Suggest dinners for the empty days from today on; days already past stay as they are. */
    fillOpenDays: () => generate.mutate({ weekStart, fromDate: today }),
  }
}

export type PlanWeekState = ReturnType<typeof usePlanWeek>
