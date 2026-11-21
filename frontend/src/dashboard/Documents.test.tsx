import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'

import { api } from '../api/client'
import { Documents } from './Documents'
import { AgentCardView } from '../app/StressCases'

vi.mock('../api/client', () => ({
  api: {
    subjects: vi.fn(),
    documents: vi.fn(),
    createSubject: vi.fn(),
    uploadDocument: vi.fn(),
    deleteDocument: vi.fn(),
    searchDocuments: vi.fn(),
  },
}))

beforeEach(() => {
  vi.resetAllMocks()
  Element.prototype.scrollIntoView = vi.fn()
})

const chapter = {
  doc_id: 'reading',
  subject_id: null,
  chapter: '',
  title: 'Probability',
  filename: 'probability.pdf',
  pages: 10,
  passages: 0,
  concepts: {},
  created_at: '2026-11-21T10:00:00Z',
  searchable: false,
  review_required: true,
  extraction_method: 'gemini',
  status: 'processing',
  progress: 3,
}

test('polls reading progress and requires review before offering practice', async () => {
  vi.mocked(api.subjects).mockResolvedValue([])
  vi.mocked(api.documents)
    .mockResolvedValueOnce([chapter])
    .mockResolvedValue([{ ...chapter, status: 'review', progress: 10 }])
  render(<Documents onAsk={vi.fn()} />)
  await screen.findByText('Checking page 3 of 10')
  expect(screen.queryByText('Check understanding')).not.toBeInTheDocument()
  await screen.findByText('Ready for review', {}, { timeout: 4000 })
  expect(screen.getByText('Review pages and formulas')).toBeEnabled()
  expect(screen.queryByText('Check understanding')).not.toBeInTheDocument()
})

test('keeps successful uploads when another file fails and retries only that file', async () => {
  vi.mocked(api.subjects).mockResolvedValue([])
  vi.mocked(api.documents).mockResolvedValue([])
  vi.mocked(api.uploadDocument)
    .mockResolvedValueOnce({ ...chapter, status: 'review' })
    .mockRejectedValueOnce(new Error('Connection interrupted'))
    .mockResolvedValueOnce({ ...chapter, doc_id: 'second', title: 'C++', status: 'review' })
  render(<Documents onAsk={vi.fn()} />)
  await screen.findByText('Add a subject and upload a chapter to begin.')
  const first = new File(['first'], 'probability.pdf', { type: 'application/pdf' })
  const second = new File(['second'], 'cpp.pdf', { type: 'application/pdf' })
  fireEvent.change(screen.getByLabelText('Upload course files'), {
    target: { files: [first, second] },
  })
  await screen.findByText('Connection interrupted')
  expect(screen.getByRole('heading', { name: 'Probability' })).toBeInTheDocument()
  fireEvent.click(screen.getByText('Try again'))
  await screen.findByRole('heading', { name: 'C++' })
  expect(api.uploadDocument).toHaveBeenCalledTimes(3)
  expect(vi.mocked(api.uploadDocument).mock.calls[2]?.[0]).toBe(second)
  expect(screen.queryByText('Connection interrupted')).not.toBeInTheDocument()
})

test('creates a subject, uploads a chapter and practises that exact document', async () => {
  vi.mocked(api.subjects).mockResolvedValue([])
  vi.mocked(api.documents).mockResolvedValue([])
  vi.mocked(api.createSubject).mockResolvedValue({ subject_id: 'subject-a', name: 'C++' })
  const doc = {
    doc_id: 'doc-a',
    subject_id: 'subject-a',
    chapter: 'STL',
    title: 'Containers',
    filename: 'stl.pdf',
    pages: 20,
    passages: 50,
    concepts: {},
    created_at: '2026-11-21T10:00:00Z',
    searchable: true,
    review_required: false,
    extraction_method: 'text',
    status: 'ready',
    progress: 0,
  }
  vi.mocked(api.uploadDocument).mockResolvedValue(doc)
  vi.mocked(api.searchDocuments).mockResolvedValue([
    {
      doc_id: 'doc-a',
      title: 'Containers',
      page: 4,
      text: 'A vector stores elements.',
      concepts: [],
      score: 0.8,
    },
  ])
  const ask = vi.fn()
  render(<Documents onAsk={ask} />)
  await screen.findByText('Add a subject and upload a chapter to begin.')
  fireEvent.click(screen.getByRole('button', { name: 'New subject' }))
  fireEvent.change(screen.getByLabelText('New subject'), { target: { value: 'C++' } })
  fireEvent.click(screen.getByText('Add subject'))
  await waitFor(() => expect(screen.getByLabelText('Subject')).toHaveValue('subject-a'))
  fireEvent.change(screen.getByLabelText('Chapter label'), { target: { value: 'STL' } })
  const file = new File(['PDF data'], 'stl.pdf', { type: 'application/pdf' })
  fireEvent.change(screen.getByLabelText('Upload course files'), { target: { files: [file] } })
  await screen.findByRole('heading', { name: 'Containers' })
  expect(api.uploadDocument).toHaveBeenCalledWith(file, 'subject-a', 'STL', false)
  fireEvent.click(screen.getByText('Check understanding'))
  expect(ask).toHaveBeenCalledWith('Quiz me on my notes [document:doc-a]')
  fireEvent.click(screen.getByText('Search this chapter'))
  fireEvent.change(screen.getByLabelText('Search your notes'), { target: { value: 'vector' } })
  fireEvent.click(screen.getByText('Search passages'))
  await screen.findByText('A vector stores elements.')
  expect(api.searchDocuments).toHaveBeenCalledWith('vector', 'doc-a')
  fireEvent.click(screen.getByText('Help me understand this'))
  expect(ask).toHaveBeenLastCalledWith('Explain this idea from my notes: vector [document:doc-a]')
})

test('renders expandable page citations on document answers', () => {
  render(
    <AgentCardView
      card={{
        card: 'sources',
        question: 'What is a vector?',
        sources: [{ title: 'STL', page: 4, text: 'A vector stores elements.' }],
      }}
      onWhy={() => {}}
    />,
  )
  expect(screen.getByText('STL · page 4')).toBeInTheDocument()
  expect(screen.getByText('A vector stores elements.')).toBeInTheDocument()
})
