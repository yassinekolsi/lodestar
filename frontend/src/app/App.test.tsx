import { render, screen } from '@testing-library/react'

import { App } from './App'

test('a first visit starts with the welcome and what Lodestar is', () => {
  render(<App />)
  expect(screen.getByRole('heading', { name: 'Welcome to Lodestar' })).toBeInTheDocument()
  expect(screen.getByText(/study coach for your course/)).toBeInTheDocument()
})
