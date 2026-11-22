import type { FeedbackKind } from '../api/types'

/** What a note to the developer can be about, in the order the popup offers them. */
export const FEEDBACK_KINDS: { kind: FeedbackKind; label: string }[] = [
  { kind: 'wrong-info', label: 'Wrong or badly shown information' },
  { kind: 'not-working', label: 'Something is not working' },
  { kind: 'idea', label: 'An idea' },
  { kind: 'other', label: 'Something else' },
]

export function feedbackKindLabel(kind: FeedbackKind | string): string {
  return FEEDBACK_KINDS.find((k) => k.kind === kind)?.label ?? 'Something else'
}
