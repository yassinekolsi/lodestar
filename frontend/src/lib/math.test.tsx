import { render, screen } from '@testing-library/react'
import { MathText, CourseText } from './math'

test('renders fractions, complements and conditional probabilities with accessible math', () => {
  const { container, rerender } = render(
    <MathText text={String.raw`$P(A\mid B)=\frac{P(A\cap B)}{P(B)}$`} />,
  )
  expect(container.querySelector('math')).not.toBeNull()
  expect(container.querySelector('.mfrac')).not.toBeNull()
  rerender(<MathText text={String.raw`$$P(\overline A)=1-P(A)$$`} />)
  expect(container.querySelector('.katex-display')).not.toBeNull()
  expect(container.querySelector('.katex-error')).toBeNull()
})

test('keeps code literal and prevents source HTML from becoming markup', () => {
  const { container } = render(
    <CourseText text={'```cpp\ncout << "$x$";\n```\n<img src=x onerror=alert(1)> $x^2$'} />,
  )
  expect(screen.getByText('cout << "$x$";')).toBeInTheDocument()
  expect(container.querySelector('pre .katex')).toBeNull()
  expect(container.querySelector('img')).toBeNull()
  expect(container.querySelector('math')).not.toBeNull()
})

test('renders probability tables without splitting conditional bars inside math', () => {
  const { container } = render(
    <CourseText
      text={
        'Before\n\n| Event | Probability |\n| --- | --- |\n| $P(A|B)$ | $\\frac{1}{4}$ |\n\nAfter'
      }
    />,
  )
  expect(screen.getAllByRole('columnheader')).toHaveLength(2)
  expect(screen.getAllByRole('cell')).toHaveLength(2)
  expect(container.querySelectorAll('td .katex')).toHaveLength(2)
  expect(screen.getByText('Before')).toBeInTheDocument()
  expect(screen.getByText('After')).toBeInTheDocument()
})
