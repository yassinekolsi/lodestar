import fs from 'node:fs'
import path from 'node:path'
import katex from 'katex'

const directory = process.argv[2]
if (!directory) throw new Error('Pass the local OCR review directory.')
let count = 0
let failed = 0
const pattern =
  /\$\$([\s\S]*?)\$\$|(?<!\\)\$((?:\\.|[^$])*?)\$|\\\[([\s\S]*?)\\\]|\\\(([\s\S]*?)\\\)/g
for (const filename of fs.readdirSync(directory).filter((name) => name.endsWith('.md'))) {
  const text = fs.readFileSync(path.join(directory, filename), 'utf8')
  for (const match of text.matchAll(pattern)) {
    count += 1
    try {
      katex.renderToString(match[1] ?? match[2] ?? match[3] ?? match[4], {
        throwOnError: true,
        trust: false,
        strict: 'ignore',
        maxExpand: 500,
        maxSize: 20,
      })
    } catch {
      failed += 1
      console.error(`${filename}: invalid formula: ${match[0].slice(0, 180)}`)
    }
  }
}
console.log(
  `${count} formulas checked; ${failed} rendering errors. This checks syntax, not transcription accuracy.`,
)
process.exitCode = failed ? 1 : 0
