import { useEffect, useState, type ReactNode } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import { Check, ChevronLeft, ChevronRight, Plus, RefreshCw, ShoppingCart, Shuffle, Trash2 } from 'lucide-react'
import PageContainer from '../components/layout/PageContainer'
import AddDinnerBand from '../components/plan/AddDinnerBand'
import WeekShoppingSheet from '../components/plan/WeekShoppingSheet'
import PlanSummary from '../components/plan/PlanSummary'
import { usePlanWeek } from '../components/plan/usePlanWeek'
import { useAuth } from '../contexts/AuthContext'
import type { MealPlanEntryDisplay } from '../api/types'
import { ownOrSourceName } from '../utils/sourceNames'
import {
  addDays,
  formatMonthDay,
  todayStr,
  weekStartOf,
  weekStartOfDateStr,
  weekTitle,
  weekdayName,
} from '../utils/week'

/**
 * Week editor at /plan/:weekStart: one plan opened up, the whole week visible
 * at once, a day per row.
 *
 * Built on the endpoints that exist: suggestions for an empty week, accept one
 * or all, swap, open the recipe. Choosing a specific recipe for a day, removing
 * or moving a meal, servings and adding people to the plan are not here yet.
 */
export default function PlanWeek() {
  const { weekStart: param = '' } = useParams<{ weekStart: string }>()
  const weekStart = weekStartOfDateStr(param)
  if (weekStart === null) {
    return <Navigate to="/plan" replace />
  }
  // Any day of the week is accepted in the URL; the week is the one holding it.
  return <WeekEditor key={weekStart} weekStart={weekStart} />
}

function WeekEditor({ weekStart }: { weekStart: string }) {
  const navigate = useNavigate()
  const { currentUser } = useAuth()
  const thisWeek = weekStartOf(new Date())
  const today = todayStr()
  const isPastWeek = weekStart < thisWeek
  const plan = usePlanWeek(weekStart, { autoFill: !isPastWeek })
  // The empty day an "Add something" band is open for, if any.
  const [addingFor, setAddingFor] = useState<string | null>(null)
  const [shoppingOpen, setShoppingOpen] = useState(false)
  const title = weekTitle(weekStart, thisWeek)

  return (
    <PageContainer>
      <div className="py-6 space-y-4">
        <div className="flex items-center justify-between">
          <Link to="/plan" className="flex items-center gap-1 text-[13px] text-olive">
            <ChevronLeft size={14} />
            All plans
          </Link>
          <div className="flex items-center gap-2">
            <button
              onClick={() => navigate(`/plan/${addDays(weekStart, -7)}`)}
              aria-label="Previous week"
              className="flex items-center justify-center w-11 h-11 rounded-full border border-warm-border bg-white text-text-secondary"
            >
              <ChevronLeft size={18} />
            </button>
            <button
              onClick={() => navigate(`/plan/${addDays(weekStart, 7)}`)}
              aria-label="Next week"
              className="flex items-center justify-center w-11 h-11 rounded-full border border-warm-border bg-white text-text-secondary"
            >
              <ChevronRight size={18} />
            </button>
          </div>
        </div>

        <PlanSummary
          title={title}
          weekStart={weekStart}
          ownerName={currentUser?.name}
          days={plan.days}
          stats={plan.stats}
          today={today}
          prominent
        />

        <div className="flex flex-wrap items-center gap-2">
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
          {/* Not for the week in progress, where days are decided one by one. */}
          {weekStart !== thisWeek && plan.stats.suggested > 0 && (
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
              aria-label="Remix this week's suggestions"
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
              className="px-3 h-9 rounded-button-sm border border-warm-btn-border bg-white text-text-secondary text-[13px] font-medium disabled:opacity-50"
            >
              Suggest for {plan.openDays === 1 ? 'the empty day' : `${plan.openDays} empty days`}
            </button>
          )}
        </div>

        {plan.notice && (
          <p role="status" className="text-sm text-olive-dark">
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

        {/* Not before the automatic attempt has started: it would flash. */}
        {plan.isEmpty && plan.autoFillStarted && !plan.suggesting && !plan.suggestFailed && (
          <div className="bg-white rounded-card border border-warm-border p-4 text-center space-y-3">
            <p className="text-sm text-text-secondary">
              {isPastWeek ? 'Nothing was planned this week.' : 'Nothing planned yet.'}
            </p>
            {!isPastWeek && (
              <button
                onClick={plan.suggest}
                className="px-4 py-2 rounded-button bg-olive text-white text-sm font-medium"
              >
                Suggest dinners
              </button>
            )}
          </div>
        )}

        {!plan.isEmpty && !plan.isLoading && !plan.isError && (
          <ul className="space-y-3" aria-label="Dinners this week">
            {plan.days.map(({ date, entry }) => (
              <DayRow
                key={date}
                date={date}
                isToday={date === today}
                entry={entry}
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
              >
                {addingFor === date && (
                  <AddDinnerBand
                    date={date}
                    taken={plan.taken}
                    adding={plan.addingDate === date}
                    error={plan.addError}
                    onAdd={(pick) => {
                      void plan.add(date, pick).then((added) => {
                        if (added) setAddingFor(null)
                      })
                    }}
                    onClose={() => setAddingFor(null)}
                  />
                )}
              </DayRow>
            ))}
          </ul>
        )}
      </div>

      <WeekShoppingSheet
        open={shoppingOpen}
        onClose={() => setShoppingOpen(false)}
        weekStart={weekStart}
        weekName={title.toLowerCase()}
      />
    </PageContainer>
  )
}

interface DayRowProps {
  date: string
  isToday: boolean
  entry: MealPlanEntryDisplay | undefined
  busy: boolean
  error: string | null
  onOpen: (entry: MealPlanEntryDisplay) => void
  onAccept: (entry: MealPlanEntryDisplay) => void
  onSwap: (entry: MealPlanEntryDisplay) => void
  onRemove: (entry: MealPlanEntryDisplay) => void
  /** The add band is open for this day. */
  addOpen: boolean
  onToggleAdd: () => void
  /** The add band itself, rendered under the day when open. */
  children?: ReactNode
}

function DayRow({
  date,
  isToday,
  entry,
  busy,
  error,
  onOpen,
  onAccept,
  onSwap,
  onRemove,
  addOpen,
  onToggleAdd,
  children,
}: DayRowProps) {
  const [imageError, setImageError] = useState(false)
  const day = weekdayName(date)
  const isDraft = entry?.status === 'draft'
  const display = entry?.display

  // A swap puts a different recipe in the same row: forget the old picture's failure.
  const imageUrl = display?.image_url ?? null
  useEffect(() => setImageError(false), [imageUrl])

  const details = display
    ? [
        ownOrSourceName(display.source_type),
        display.prep_time_minutes ? `${display.prep_time_minutes} min` : null,
      ]
        .filter(Boolean)
        .join(' · ')
    : null

  return (
    <li className="bg-white rounded-card border border-warm-border overflow-hidden">
      <div className="px-3 pt-2.5 flex items-baseline gap-2">
        <p
          className={`text-[11px] font-medium uppercase tracking-wide ${
            isToday ? 'text-olive' : 'text-text-secondary'
          }`}
        >
          {isToday ? `Today · ${day}` : day}
        </p>
        <p className="text-[11px] text-text-tertiary">{formatMonthDay(date)}</p>
      </div>

      {!entry || !display ? (
        <div className="px-3 pt-1 pb-3 flex items-center justify-between gap-3">
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
        </div>
      ) : (
        <div className="p-3 pt-2 flex gap-3">
          <button
            onClick={() => onOpen(entry)}
            aria-label={`Open ${display.name}`}
            className={`flex-shrink-0 w-[112px] aspect-[4/3] rounded-image-card bg-warm-gray overflow-hidden${
              isDraft ? ' opacity-70' : ''
            }`}
          >
            {imageUrl && !imageError ? (
              <img
                src={imageUrl}
                alt=""
                className="w-full h-full object-cover"
                onError={() => setImageError(true)}
              />
            ) : (
              <span className="w-full h-full flex items-center justify-center text-text-tertiary text-xs">
                No image
              </span>
            )}
          </button>

          <div className="min-w-0 flex-1 flex flex-col">
            <button
              onClick={() => onOpen(entry)}
              className={`text-left${isDraft ? ' opacity-70' : ''}`}
            >
              <span className="block text-[14px] font-medium text-text-primary leading-tight line-clamp-2">
                {display.name}
              </span>
              <span className="block mt-0.5 text-[12px] text-text-secondary">{details}</span>
            </button>

            {isDraft ? (
              <div className="mt-auto pt-2 flex gap-2">
                <button
                  onClick={() => onAccept(entry)}
                  disabled={busy}
                  aria-label={`Accept ${day} dinner`}
                  className="flex items-center gap-1.5 px-3 h-9 rounded-button-sm bg-olive text-white text-[13px] font-medium disabled:opacity-50"
                >
                  <Check size={14} />
                  Accept
                </button>
                <button
                  onClick={() => onSwap(entry)}
                  disabled={busy}
                  aria-label={`Swap ${day} dinner`}
                  className="flex items-center gap-1.5 px-3 h-9 rounded-button-sm border border-warm-btn-border text-text-secondary text-[13px] font-medium disabled:opacity-50"
                >
                  <RefreshCw size={14} />
                  Swap
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
              <div className="mt-auto pt-2 flex items-center justify-between gap-2">
                <p className="flex items-center gap-1 text-[12px] text-olive-dark">
                  <Check size={13} />
                  Planned
                </p>
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
          </div>
        </div>
      )}

      {error && (
        <p role="alert" className="px-3 pb-3 text-[12px] text-terra-dark">
          {error}
        </p>
      )}

      {children && <div className="px-3 pb-3">{children}</div>}
    </li>
  )
}
