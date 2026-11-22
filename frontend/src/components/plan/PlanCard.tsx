import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Check, ChevronRight, Plus, RefreshCw, ShoppingCart, Shuffle, Trash2 } from 'lucide-react'
import type { MealPlanEntryDisplay } from '../../api/types'
import { ownOrSourceName } from '../../utils/sourceNames'
import { weekdayName } from '../../utils/week'
import AddDinnerBand from './AddDinnerBand'
import WeekShoppingSheet from './WeekShoppingSheet'
import PlanSummary from './PlanSummary'
import { usePlanWeek } from './usePlanWeek'

interface PlanCardProps {
  weekStart: string
  title: string
  ownerName: string | undefined
  today: string
  /** Large: the week in front of you. Compact: a sample week further out. */
  size: 'large' | 'compact'
  /** Fill the week with suggestions when it has nothing. */
  autoFill: boolean
  /** Offer "Accept all". Off for the week in progress, where days are decided one by one. */
  offerAcceptAll: boolean
}

/**
 * One week of the plan as a single card: who and when at the top, the week's
 * dinners as a carousel inside it. Quick decisions (accept, swap) happen here;
 * the week editor at /plan/:weekStart shows the whole week at once.
 */
export default function PlanCard({
  weekStart,
  title,
  ownerName,
  today,
  size,
  autoFill,
  offerAcceptAll,
}: PlanCardProps) {
  const plan = usePlanWeek(weekStart, { autoFill })
  const large = size === 'large'
  // The empty day an "Add something" band is open for, if any.
  const [addingFor, setAddingFor] = useState<string | null>(null)
  const [shoppingOpen, setShoppingOpen] = useState(false)

  // Open the current week's carousel at today, not at the start of the week.
  const listRef = useRef<HTMLUListElement>(null)
  const showsDinners = !plan.isEmpty && !plan.isLoading && !plan.isError
  useEffect(() => {
    const list = listRef.current
    const todayCard = list?.querySelector<HTMLElement>('[data-today="true"]')
    if (!showsDinners || !list || !todayCard) return
    const gutter = 16
    list.scrollLeft +=
      todayCard.getBoundingClientRect().left - list.getBoundingClientRect().left - gutter
  }, [showsDinners])

  return (
    <section
      aria-label={title}
      className="bg-white rounded-card-lg border border-warm-border overflow-hidden"
    >
      <div className="p-4 space-y-3">
        <PlanSummary
          title={title}
          weekStart={weekStart}
          ownerName={ownerName}
          days={plan.days}
          stats={plan.stats}
          today={today}
        />

        <div className="flex flex-wrap items-center gap-2">
          {offerAcceptAll && plan.stats.suggested > 0 && (
            <button
              onClick={plan.acceptAll}
              disabled={plan.acceptingAll}
              className="flex items-center gap-1.5 px-3 h-9 rounded-button-sm bg-olive text-white text-[13px] font-medium disabled:opacity-50"
            >
              <Check size={14} />
              {plan.acceptingAll ? 'Accepting...' : `Accept all ${plan.stats.suggested}`}
            </button>
          )}
          {plan.remixable > 0 && (
            <button
              onClick={plan.remix}
              disabled={plan.remixing}
              aria-label={`Remix ${title.toLowerCase()}`}
              className="flex items-center gap-1.5 px-3 h-9 rounded-button-sm border border-warm-btn-border bg-white text-text-secondary text-[13px] font-medium disabled:opacity-50"
            >
              <Shuffle size={14} />
              {plan.remixing ? 'Remixing...' : 'Remix'}
            </button>
          )}
          {plan.openDays > 0 && (
            <button
              onClick={plan.fillOpenDays}
              disabled={plan.suggesting}
              className="px-3 h-9 rounded-button-sm border border-warm-btn-border text-text-secondary text-[13px] font-medium disabled:opacity-50"
            >
              Fill {plan.openDays === 1 ? 'empty day' : `${plan.openDays} empty days`}
            </button>
          )}
          {plan.stats.planned > 0 && (
            <button
              onClick={() => setShoppingOpen(true)}
              aria-label={`Grocery list for ${title.toLowerCase()}`}
              className="flex items-center gap-1.5 px-3 h-9 rounded-button-sm border border-warm-btn-border bg-white text-text-secondary text-[13px] font-medium"
            >
              <ShoppingCart size={14} />
              Grocery list
            </button>
          )}
          <Link
            to={`/plan/${weekStart}`}
            aria-label={`Edit ${title.toLowerCase()}`}
            className="flex items-center gap-1 px-3 h-9 rounded-button-sm border border-warm-btn-border text-text-secondary text-[13px] font-medium"
          >
            Edit week
            <ChevronRight size={14} />
          </Link>
        </div>

        {plan.notice && (
          <p role="status" className="text-xs text-olive-dark">
            {plan.notice}
          </p>
        )}
        {plan.isLoading && <p className="text-sm text-text-secondary">Loading...</p>}
        {plan.isError && (
          <p className="text-sm text-text-secondary">
            Could not load this week.{' '}
            <button onClick={plan.retryLoad} className="text-olive underline">
              Try again
            </button>
          </p>
        )}
        {plan.suggesting && (
          <p className="text-sm text-text-secondary">Choosing dinners for this week...</p>
        )}
        {plan.suggestFailed && (
          <p className="text-sm text-text-secondary">
            Could not suggest a week yet.{' '}
            <button onClick={plan.suggest} className="text-olive underline">
              Try again
            </button>
          </p>
        )}
        {plan.isEmpty && plan.autoFillStarted && !plan.suggesting && !plan.suggestFailed && (
          <p className="text-sm text-text-secondary">
            Nothing planned yet.{' '}
            <button onClick={plan.suggest} className="text-olive underline">
              Suggest dinners
            </button>
          </p>
        )}
      </div>

      {showsDinners && (
        <ul
          ref={listRef}
          aria-label={`${title} dinners`}
          className="flex gap-3 overflow-x-auto px-4 pb-4 scrollbar-hide"
        >
          {plan.days.map(({ date, entry }) => (
            <MealCard
              key={date}
              date={date}
              isToday={date === today}
              entry={entry}
              large={large}
              busy={plan.isBusy(entry)}
              error={plan.errorFor(entry)}
              onOpen={plan.open}
              onAccept={plan.accept}
              onSwap={plan.swap}
              onRemove={plan.remove}
              addOpen={addingFor === date}
              onToggleAdd={() => {
                plan.clearAddError()
                setAddingFor((current) => (current === date ? null : date))
              }}
            />
          ))}
        </ul>
      )}

      {showsDinners && addingFor && (
        <div className="px-4 pb-4">
          <AddDinnerBand
            date={addingFor}
            taken={plan.taken}
            adding={plan.addingDate === addingFor}
            error={plan.addError}
            onAdd={(pick) => {
              void plan.add(addingFor, pick).then((added) => {
                if (added) setAddingFor(null)
              })
            }}
            onClose={() => setAddingFor(null)}
          />
        </div>
      )}

      <WeekShoppingSheet
        open={shoppingOpen}
        onClose={() => setShoppingOpen(false)}
        weekStart={weekStart}
        weekName={title.toLowerCase()}
      />
    </section>
  )
}

interface MealCardProps {
  date: string
  isToday: boolean
  entry: MealPlanEntryDisplay | undefined
  large: boolean
  busy: boolean
  error: string | null
  onOpen: (entry: MealPlanEntryDisplay) => void
  onAccept: (entry: MealPlanEntryDisplay) => void
  onSwap: (entry: MealPlanEntryDisplay) => void
  onRemove: (entry: MealPlanEntryDisplay) => void
  /** The add band is open for this day. */
  addOpen: boolean
  onToggleAdd: () => void
}

function MealCard({
  date,
  isToday,
  entry,
  large,
  busy,
  error,
  onOpen,
  onAccept,
  onSwap,
  onRemove,
  addOpen,
  onToggleAdd,
}: MealCardProps) {
  const [imageError, setImageError] = useState(false)
  const day = weekdayName(date)
  const display = entry?.display
  const isDraft = entry?.status === 'draft'

  // A swap puts a different recipe in the same card: forget the old picture's failure.
  const imageUrl = display?.image_url ?? null
  useEffect(() => setImageError(false), [imageUrl])

  const width = large ? 'w-[232px]' : 'w-[168px]'
  const dayBadge = (
    <span
      className={`absolute top-2 left-2 px-2 py-0.5 rounded-pill text-[11px] font-medium uppercase tracking-wide ${
        isToday ? 'bg-olive text-white' : 'bg-white/90 text-text-secondary'
      }`}
    >
      {isToday ? `Today · ${day.slice(0, 3)}` : day.slice(0, 3)}
    </span>
  )

  if (!entry || !display) {
    return (
      <li
        data-today={isToday}
        aria-label={`${day}: nothing planned`}
        className={`relative flex-shrink-0 ${width} rounded-card border border-dashed border-warm flex flex-col items-center justify-center gap-3 min-h-[160px]`}
      >
        {dayBadge}
        <p className="text-[13px] text-text-tertiary">Nothing planned</p>
        <button
          onClick={onToggleAdd}
          aria-label={`Add something for ${day}`}
          aria-expanded={addOpen}
          className="flex items-center gap-1.5 px-3 h-9 rounded-button-sm border border-warm-btn-border bg-white text-text-secondary text-[13px] font-medium"
        >
          <Plus size={14} />
          Add something
        </button>
      </li>
    )
  }

  const details = [
    ownOrSourceName(display.source_type),
    display.prep_time_minutes ? `${display.prep_time_minutes} min` : null,
  ]
    .filter(Boolean)
    .join(' · ')

  return (
    <li
      data-today={isToday}
      aria-label={`${day}: ${display.name}`}
      className={`flex-shrink-0 ${width} flex flex-col rounded-card border border-warm-border bg-white overflow-hidden`}
    >
      <button
        onClick={() => onOpen(entry)}
        aria-label={`Open ${display.name}`}
        className="relative block w-full aspect-[4/3] bg-warm-gray"
      >
        {imageUrl && !imageError ? (
          <img
            src={imageUrl}
            alt=""
            className={`w-full h-full object-cover${isDraft ? ' opacity-70' : ''}`}
            onError={() => setImageError(true)}
          />
        ) : (
          <span className="w-full h-full flex items-center justify-center text-text-tertiary text-xs">
            No image
          </span>
        )}
        {dayBadge}
        {!isDraft && (
          <span
            aria-hidden="true"
            className="absolute top-2 right-2 flex items-center justify-center w-6 h-6 rounded-full bg-olive text-white"
          >
            <Check size={14} />
          </span>
        )}
      </button>

      <div className="flex-1 flex flex-col p-3 gap-2">
        <div className={isDraft ? 'opacity-70' : ''}>
          <p
            className={`font-medium text-text-primary leading-tight line-clamp-2 ${
              large ? 'text-[14px]' : 'text-[13px]'
            }`}
          >
            {display.name}
          </p>
          <p className="mt-0.5 text-[12px] text-text-secondary">{details}</p>
        </div>

        {isDraft ? (
          <div className="mt-auto flex gap-2">
            <button
              onClick={() => onAccept(entry)}
              disabled={busy}
              aria-label={`Accept ${day} dinner`}
              className="flex items-center justify-center gap-1.5 flex-1 h-9 rounded-button-sm bg-olive text-white text-[13px] font-medium disabled:opacity-50"
            >
              <Check size={14} />
              {large && 'Accept'}
            </button>
            <button
              onClick={() => onSwap(entry)}
              disabled={busy}
              aria-label={`Swap ${day} dinner`}
              className="flex items-center justify-center gap-1.5 flex-1 h-9 rounded-button-sm border border-warm-btn-border text-text-secondary text-[13px] font-medium disabled:opacity-50"
            >
              <RefreshCw size={14} />
              {large && 'Swap'}
            </button>
            <button
              onClick={() => onRemove(entry)}
              disabled={busy}
              aria-label={`Remove ${day} dinner`}
              className="flex items-center justify-center w-9 h-9 flex-shrink-0 rounded-button-sm border border-warm-btn-border text-text-secondary disabled:opacity-50"
            >
              <Trash2 size={14} />
            </button>
          </div>
        ) : (
          <div className="mt-auto flex items-center justify-between gap-2">
            <p className="text-[12px] text-olive-dark">Planned</p>
            <button
              onClick={() => onRemove(entry)}
              disabled={busy}
              aria-label={`Remove ${day} dinner`}
              className="flex items-center justify-center w-9 h-9 flex-shrink-0 rounded-button-sm border border-warm-btn-border text-text-secondary disabled:opacity-50"
            >
              <Trash2 size={14} />
            </button>
          </div>
        )}

        {error && (
          <p role="alert" className="text-[12px] text-terra-dark">
            {error}
          </p>
        )}
      </div>
    </li>
  )
}
