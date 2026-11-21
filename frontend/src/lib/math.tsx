import { useEffect, useRef } from 'react'
import { renderMath } from './renderMath'

export function MathText({ text }: { text: string }) {
  const target = useRef<HTMLSpanElement>(null)
  useEffect(() => {
    const node = target.current
    if (!node) return
    node.replaceChildren(document.createTextNode(text))
    renderMath(node)
  }, [text])
  return (
    <span className="math-text" ref={target}>
      {text}
    </span>
  )
}

export function CourseText({ text }: { text: string }) {
  return (
    <>
      {text.split(/(```[^\n]*\n[\s\S]*?```)/g).map((part, i) =>
        part.startsWith('```') ? (
          <pre className="course-code" key={i}>
            <code>{part.replace(/^```[^\n]*\n|```$/g, '')}</code>
          </pre>
        ) : (
          <MathText key={i} text={part} />
        ),
      )}
    </>
  )
}
