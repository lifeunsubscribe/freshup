import { Check, UtensilsCrossed } from 'lucide-react'
import type { PlanDay, PlanStats } from './usePlanWeek'
import { formatDuration, formatWeekRange, weekdayName } from '../../utils/week'

/**
 * The top of a plan: which week, whose plan, and how far along it is.
 *
 * People: this is the place for the plan's collaborators, the people who plan
 * the week together. Today a plan has one person, its owner. Who eats a given
 * dinner is a property of that dinner and belongs on the meal, shown only when
 * it differs from the plan's people.
 */
interface PlanSummaryProps {
  title: string
  weekStart: string
  ownerName: string | undefined
  days: PlanDay[]
  stats: PlanStats
  today: string
  /** Larger title for the page-level header of the week editor. */
  prominent?: boolean
}

export default function PlanSummary({
  title,
  weekStart,
  ownerName,
  days,
  stats,
  today,
  prominent = false,
}: PlanSummaryProps) {
  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2
            className={`font-medium text-text-primary leading-tight ${
              prominent ? 'text-[22px]' : 'text-[17px]'
            }`}
          >
            {title}
            <span className="text-olive">.</span>
          </h2>
          <p className="text-xs text-text-secondary mt-0.5">{formatWeekRange(weekStart)}</p>
        </div>
        <People ownerName={ownerName} />
      </div>

      {/* The meals this plan covers. Dinner is the only one so far; breakfast,
          lunch and the rest will sit beside it when they can be planned. */}
      <p
        aria-label="Meals in this plan: dinner"
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-pill bg-cream-pill text-[11px] font-medium uppercase tracking-wide text-text-secondary"
      >
        <UtensilsCrossed size={12} aria-hidden="true" />
        Dinner
      </p>

      <DayStrip days={days} today={today} />

      <p className="text-xs text-text-secondary">{summaryLine(stats)}</p>
    </div>
  )
}

function People({ ownerName }: { ownerName: string | undefined }) {
  const initial = ownerName?.trim().charAt(0).toUpperCase() || '?'
  return (
    <div className="flex items-center gap-2 flex-shrink-0" aria-label="People on this plan: just you">
      <span className="text-xs text-text-secondary">Just you</span>
      <span
        aria-hidden="true"
        className="flex items-center justify-center w-7 h-7 rounded-full bg-olive text-white text-[12px] font-medium"
      >
        {initial}
      </span>
    </div>
  )
}

/** Seven marks, one per day: accepted, suggested or nothing. */
function DayStrip({ days, today }: { days: PlanDay[]; today: string }) {
  return (
    <ol className="grid grid-cols-7 gap-1.5" aria-label="The week at a glance">
      {days.map(({ date, entry }) => {
        const day = weekdayName(date)
        const state = !entry ? 'nothing planned' : entry.status === 'draft' ? 'suggested' : 'planned'
        const isToday = date === today
        return (
          <li key={date} aria-label={`${day}: ${state}`} className="flex flex-col items-center gap-1">
            <span
              aria-hidden="true"
              className={`text-[10px] font-medium uppercase ${
                isToday ? 'text-olive' : 'text-text-tertiary'
              }`}
            >
              {day.slice(0, 3)}
            </span>
            <span
              aria-hidden="true"
              className={`flex items-center justify-center w-full h-5 rounded-pill ${
                state === 'planned'
                  ? 'bg-olive text-white'
                  : state === 'suggested'
                    ? 'bg-olive/20'
                    : 'border border-dashed border-warm'
              }`}
            >
              {state === 'planned' && <Check size={12} />}
            </span>
          </li>
        )
      })}
    </ol>
  )
}

function summaryLine(stats: PlanStats): string {
  if (stats.planned === 0 && stats.suggested === 0) return 'Nothing planned.'
  const parts = [
    stats.planned > 0 ? `${stats.planned} planned` : null,
    stats.suggested > 0 ? `${stats.suggested} suggested` : null,
    stats.minutes > 0 ? `about ${formatDuration(stats.minutes)} of cooking` : null,
  ]
  return parts.filter(Boolean).join(' · ')
}
