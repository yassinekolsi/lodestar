# Course formula rendering

This work package adds KaTeX **0.19.1**, pinned exactly in package.json and package-lock.json.
No existing package version is upgraded. KaTeX ships its TypeScript definitions.

Course text accepts `$...$` and `\(...\)` inline, and `$$...$$` and `\[...\]` for display math.
The same renderer handles chapter review, source passages, explanations and quiz content. Code
fences preserve literal C++ text. Markdown tables render as native tables, retaining conditional
bars inside formula cells. Rendering emits HTML and accessible MathML, with `trust: false`,
bounded macro expansion and React text nodes so source HTML cannot become executable markup.

Chunking preserves complete formula blocks, tables and code fences even when they exceed the normal
passage target. Backend review checks reject unbalanced delimiters, braces and unmatched
`\left`/`\right`. These are syntax checks, not proof checking or OCR accuracy estimates.

Validation: `frontend/src/lib/math.test.tsx` checks fractions, conditional probabilities,
complements, literal code and HTML injection. Backend document tests check formula chunking and
review rejection. `node scripts/check-math.mjs /tmp/ocr-review` checks locally exported review
Markdown against KaTeX; the latest local scan audit rendered 664 expressions without syntax errors.
