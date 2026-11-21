import { useEffect, useRef } from 'react'
import { renderMath } from './renderMath'

function tableCells(line: string): string[] {
  const cells = ['']
  // Consume math as a whole so the conditional bar in $P(A|B)$ stays in its cell.
  const tokens =
    line
      .trim()
      .slice(1, -1)
      .match(/\$(?:\\.|[^$])*?\$|\\\([\s\S]*?\\\)|\\\||\||./g) ?? []
  for (const token of tokens) {
    if (token === '|') cells.push('')
    else cells[cells.length - 1] = (cells.at(-1) ?? '') + (token === '\\|' ? '|' : token)
  }
  return cells.map((cell) => cell.trim())
}

function Prose({ text }: { text: string }) {
  const table = /(^\|[^\n]+\|[ \t]*\n\|[ :|-]+\|[ \t]*(?:\n\|[^\n]+\|[ \t]*)+)/gm
  const parts = []
  let start = 0
  for (const match of text.matchAll(table)) {
    parts.push(
      <MathText key={`before-${String(match.index)}`} text={text.slice(start, match.index)} />,
    )
    const rows = match[0].trim().split('\n').map(tableCells)
    const header = rows[0] ?? []
    parts.push(
      <div className="course-table" key={`table-${String(match.index)}`}>
        <table>
          <thead>
            <tr>
              {header.map((cell, i) => (
                <th scope="col" key={i}>
                  <MathText text={cell} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(2).map((row, i) => (
              <tr key={i}>
                {row.map((cell, j) => (
                  <td key={j}>
                    <MathText text={cell} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>,
    )
    start = match.index + match[0].length
  }
  parts.push(<MathText key="after" text={text.slice(start)} />)
  return <>{parts}</>
}

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
          <Prose key={i} text={part} />
        ),
      )}
    </>
  )
}
