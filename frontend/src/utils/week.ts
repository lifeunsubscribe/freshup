/**
 * Week arithmetic for the meal plan. Dates are local calendar days written
 * as YYYY-MM-DD; a plan week runs Sunday to Saturday, and its Sunday is the
 * week_start the plan endpoints take (src/services/plan_week.py).
 */

function toDateStr(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function fromDateStr(dateStr: string): Date {
  const [y, m, d] = dateStr.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function todayStr(): string {
  return toDateStr(new Date())
}

/** The first day (Sunday) of the plan week that holds `date`. */
export function weekStartOf(date: Date): string {
  const sunday = new Date(date)
  sunday.setDate(date.getDate() - date.getDay()) // getDay(): 0=Sun...6=Sat
  return toDateStr(sunday)
}

export function addDays(dateStr: string, n: number): string {
  const date = fromDateStr(dateStr)
  date.setDate(date.getDate() + n)
  return toDateStr(date)
}

/** The seven days of the week starting at `weekStart`. */
export function weekDates(weekStart: string): string[] {
  return Array.from({ length: 7 }, (_, i) => addDays(weekStart, i))
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

/** "Nov 16" */
export function formatMonthDay(dateStr: string): string {
  const date = fromDateStr(dateStr)
  return `${MONTHS[date.getMonth()]} ${date.getDate()}`
}

/** "Monday" */
export function weekdayName(dateStr: string): string {
  return WEEKDAYS[fromDateStr(dateStr).getDay()]
}

/** "Nov 16 – 22", or "Nov 30 – Dec 6" across a month end. */
export function formatWeekRange(weekStart: string): string {
  const first = fromDateStr(weekStart)
  const last = fromDateStr(addDays(weekStart, 6))
  const end =
    first.getMonth() === last.getMonth()
      ? String(last.getDate())
      : `${MONTHS[last.getMonth()]} ${last.getDate()}`
  return `${MONTHS[first.getMonth()]} ${first.getDate()} – ${end}`
}

/** The start of the plan week holding the day written as YYYY-MM-DD, or null if it is not a date. */
export function weekStartOfDateStr(dateStr: string): string | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) return null
  const date = fromDateStr(dateStr)
  return Number.isNaN(date.getTime()) ? null : weekStartOf(date)
}

/** "This week", "Next week", "Last week", otherwise "Week of Dec 7". */
export function weekTitle(weekStart: string, thisWeek: string): string {
  if (weekStart === thisWeek) return 'This week'
  if (weekStart === addDays(thisWeek, 7)) return 'Next week'
  if (weekStart === addDays(thisWeek, -7)) return 'Last week'
  return `Week of ${formatMonthDay(weekStart)}`
}

/** "45 min", "3 h", "3 h 5 min" */
export function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  if (h === 0) return `${m} min`
  return m === 0 ? `${h} h` : `${h} h ${m} min`
}
