import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
import { api } from '../api/client'
import type { DocumentView } from '../api/types'
import { DocumentReview } from './DocumentReview'

vi.mock('../api/client', () => ({
  api: { documentPages: vi.fn(), documentOriginal: vi.fn(), reviewDocument: vi.fn() },
}))
const doc: DocumentView = {
  doc_id: 'chapter',
  title: 'Probability',
  filename: 'probability.md',
  pages: 2,
  passages: 2,
  concepts: {},
  created_at: '',
  status: 'review',
  progress: 2,
  searchable: false,
  review_required: true,
  extraction_method: 'text',
  chapter: '',
}
const texts = [
  'The first section explains random events.',
  'The second section explains conditional probability: $P(A|B)=0.5$.',
]
beforeEach(() => {
  vi.resetAllMocks()
  Element.prototype.scrollIntoView = vi.fn()
  vi.mocked(api.documentPages).mockResolvedValue(
    texts.map((text, i) => ({ page: i + 1, text, warnings: [] })),
  )
})

test('shows the entire chapter without pagination and validates while preserving page boundaries', async () => {
  const saved = { ...doc, status: 'ready', review_required: false }
  vi.mocked(api.reviewDocument).mockResolvedValue(saved)
  const onSaved = vi.fn()
  render(<DocumentReview doc={doc} onSaved={onSaved} onClose={vi.fn()} />)
  await screen.findByText(texts[0] ?? '', { selector: '.math-text' })
  expect(
    screen.getByText(/The second section explains/, { selector: '.math-text' }),
  ).toBeInTheDocument()
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Validate chapter' }))
  await waitFor(() => {
    expect(onSaved).toHaveBeenCalledWith(saved)
  })
  expect(api.reviewDocument).toHaveBeenCalledWith('chapter', texts)
})

test('shows a failed save, allows corrections, and retries instead of staying disabled', async () => {
  let reject: (error: Error) => void = () => {}
  vi.mocked(api.reviewDocument)
    .mockImplementationOnce(
      () =>
        new Promise((_, fail) => {
          reject = fail
        }),
    )
    .mockResolvedValueOnce({ ...doc, status: 'ready', review_required: false })
  const onSaved = vi.fn()
  render(<DocumentReview doc={doc} onSaved={onSaved} onClose={vi.fn()} />)
  await screen.findByText(texts[0] ?? '', { selector: '.math-text' })
  fireEvent.click(screen.getByText('Validate chapter'))
  expect(screen.getByText('Saving chapter…')).toBeDisabled()
  reject(new Error('Fix unbalanced formula delimiters or braces before approving.'))
  await screen.findByRole('alert')
  expect(screen.getByText('Validate chapter')).toBeEnabled()
  const edit = screen.getAllByText('Edit extracted text')[1]
  const input = screen.getAllByLabelText('Extracted page text')[1]
  if (!edit || !input) throw new Error('Missing second section editor')
  fireEvent.click(edit)
  fireEvent.change(input, {
    target: { value: 'Corrected second section.' },
  })
  fireEvent.click(screen.getByText('Validate chapter'))
  await waitFor(() => {
    expect(onSaved).toHaveBeenCalled()
  })
  expect(api.reviewDocument).toHaveBeenLastCalledWith('chapter', [
    texts[0],
    'Corrected second section.',
  ])
})
