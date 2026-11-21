import { expect, test } from '@playwright/test'
import { prepare } from './helpers'

test('student creates a subject, uploads a chapter, searches and starts its quiz', async ({
  page,
}) => {
  await prepare(page)
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Your course. Your pace.' })).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByRole('button', { name: 'Choose files', exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(391)
  await page.screenshot({ path: 'test-results/documents-mobile.png', fullPage: true })
  await page.setViewportSize({ width: 1280, height: 800 })
  await page.getByRole('button', { name: 'Start studying', exact: true }).click()
  await page.getByRole('button', { name: 'Documents', exact: true }).click()
  await page.getByRole('button', { name: 'New subject', exact: true }).click()
  await page.getByLabel('New subject').fill('C++ foundations')
  await page.getByRole('button', { name: 'Add subject', exact: true }).click()
  await expect(page.getByLabel('Subject', { exact: true })).not.toHaveValue('')
  await page.getByText('Import options', { exact: true }).click()
  await page.getByLabel('Chapter label').fill('Structures')
  await page.getByLabel('Upload course files').setInputFiles({
    name: 'structures.md',
    mimeType: 'text/markdown',
    buffer: Buffer.from(
      'Data structures\n\nA stack is a collection where the last item added is removed first. A queue is a collection where the first item added is removed first. A tree is a collection with parent and child relationships. A graph is a collection of vertices connected by edges.',
    ),
  })
  await expect(page.getByRole('heading', { name: 'Data structures', exact: true })).toBeVisible({
    timeout: 90_000,
  })
  await page.getByRole('button', { name: 'Review pages and formulas', exact: true }).click()
  await expect(page.locator('.document-review__text')).toContainText('A stack is a collection')
  await page.getByRole('button', { name: 'Validate chapter', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Check understanding', exact: true })).toBeVisible({
    timeout: 30_000,
  })
  await page.screenshot({ path: 'test-results/documents-library.png', fullPage: true })
  await page.getByRole('button', { name: 'Search this chapter', exact: true }).click()
  await page.getByLabel('Search your notes').fill('stack collection last item')
  await page.getByRole('button', { name: 'Search passages', exact: true }).click()
  await expect(page.getByText('Data structures · page 1', { exact: true })).toBeVisible({
    timeout: 30_000,
  })
  await page.getByRole('button', { name: 'Review pages and formulas', exact: true }).click()
  await expect(page.locator('.document-review__text')).toContainText('A stack is a collection')
  await page.getByRole('button', { name: 'Close review', exact: true }).click()
  await page.getByRole('button', { name: 'Check understanding', exact: true }).click()
  await expect(page.getByTestId('suggestion')).toBeVisible({ timeout: 90_000 })
  await expect(page.getByTestId('suggestion')).toContainText('Data structures')
  await page.getByRole('button', { name: "Let's go" }).click()
  await page.getByRole('button', { name: 'Start', exact: true }).click()
  await expect(page.getByTestId('quiz-stem')).toBeVisible()
  await page.getByTestId('choice-0').click()
  await page.getByTestId('sure-2').click()
  await expect(page.getByTestId('quiz-feedback')).toContainText('Page 1')
  await page.screenshot({ path: 'test-results/documents-quiz.png', fullPage: true })
})

test('reviews a whole multi-page chapter and validates it without a checkbox', async ({ page }) => {
  await prepare(page)
  await page.goto('/')
  const first =
    'Whole chapter\n\nA stack is a collection where the last item added is removed first. A queue is a collection where the first item added is removed first.'
  const second =
    'Conditional probability\n\nThe probability of A given B is $P(A|B)=P(A \\cap B)/P(B)$. The event B must have positive probability. This formula relates the intersection of two events to a conditional probability.'
  await page
    .getByLabel('Upload course files')
    .setInputFiles({
      name: 'whole-chapter.md',
      mimeType: 'text/markdown',
      buffer: Buffer.from(first + '\f' + second),
    })
  await page
    .getByRole('button', { name: 'Review pages and formulas', exact: true })
    .click({ timeout: 30000 })
  const review = page.getByRole('region', { name: 'Review extracted pages' })
  await expect(review.locator('.document-review__text')).toHaveCount(2)
  await expect(review.locator('.document-review__text').first()).toContainText(
    'A stack is a collection',
  )
  await expect(review.locator('.document-review__text').last()).toContainText(
    'Conditional probability',
  )
  await expect(review.getByRole('combobox')).toHaveCount(0)
  await expect(review.getByRole('checkbox')).toHaveCount(0)
  await page.screenshot({ path: 'test-results/whole-chapter-review.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(391)
  await page.screenshot({ path: 'test-results/whole-chapter-mobile.png', fullPage: true })
  await review.getByRole('button', { name: 'Validate chapter', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Check understanding', exact: true })).toBeVisible({
    timeout: 10000,
  })
  await expect(page.getByText('Ready to study', { exact: true })).toBeVisible()
})
