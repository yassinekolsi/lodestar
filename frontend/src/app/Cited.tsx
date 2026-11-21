import type { ReactNode } from 'react'
import { MathText } from '../lib/math'

const CITE = /\[([FDKM]\d+(?:\s*,\s*[FDKM]\d+)*)\]/g

/** Lodestar's text with its citations as small chips. A decision citation opens its "why" card
 * (docs/plan/09: every number traces to a fact, every choice to a decision). */
export function Cited({
  text,
  refs,
  onWhy,
}: {
  text: string
  refs?: Record<string, string> | undefined
  onWhy?: ((decisionId: string) => void) | undefined
}) {
  const parts: ReactNode[] = []
  let last = 0
  for (const match of text.matchAll(CITE)) {
    const at = match.index
    parts.push(<MathText key={`text-${String(at)}`} text={text.slice(last, at)} />)
    for (const id of (match[1] ?? '').split(/\s*,\s*/)) {
      const ref = refs?.[id]
      parts.push(
        ref && onWhy ? (
          <button
            key={`${String(at)}-${id}`}
            type="button"
            className="cite cite--why"
            aria-label={`Why? (${id})`}
            onClick={() => {
              onWhy(ref)
            }}
          >
            {id}
          </button>
        ) : (
          <span key={`${String(at)}-${id}`} className="cite">
            {id}
          </span>
        ),
      )
    }
    last = at + match[0].length
  }
  parts.push(<MathText key="tail" text={text.slice(last)} />)
  return <>{parts}</>
}
