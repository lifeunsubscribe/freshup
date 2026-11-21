/**
 * Week arithmetic for the meal plan. Dates are local calendar days written
 * as YYYY-MM-DD; a week starts on Monday, which is what GET /plan/week takes.
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

/** The Monday of the week that holds `date`. */
export function mondayOf(date: Date): string {
  const day = date.getDay() // 0=Sun, 1=Mon...6=Sat
  const monday = new Date(date)
  monday.setDate(date.getDate() + (day === 0 ? -6 : 1 - day))
  return toDateStr(monday)
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
