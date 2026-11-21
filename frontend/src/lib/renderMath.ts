import renderMathInElement from 'katex/contrib/auto-render'
import 'katex/dist/katex.min.css'

/** User text stays text; trusted LaTeX commands and external links are disabled. */
export function renderMath(element: HTMLElement): void {
  renderMathInElement(element, {
    delimiters: [
      { left: '$$', right: '$$', display: true },
      { left: '\\[', right: '\\]', display: true },
      { left: '\\(', right: '\\)', display: false },
      { left: '$', right: '$', display: false },
    ],
    throwOnError: false,
    trust: false,
    strict: 'ignore',
    maxExpand: 500,
    maxSize: 20,
    output: 'htmlAndMathml',
  })
}
