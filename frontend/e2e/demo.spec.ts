import { expect, test } from '@playwright/test'
import { prepare } from './helpers'

test('demo person opens Alex and switches back without a local mode navbar label', async ({
  page,
}) => {
  await prepare(page)
  await page.goto('/')
  await page.getByRole('button', { name: 'Start studying', exact: true }).click()
  const own = await page.evaluate(() => localStorage.getItem('lodestar.token'))
  await page.getByRole('switch', { name: 'Demo person', exact: true }).click()
  await expect(page.getByText('Demo: Alex', { exact: true })).toBeVisible({ timeout: 60000 })
  await expect(page.getByText('Local mode', { exact: true })).toHaveCount(0)
  await page.getByRole('switch', { name: 'Demo person', exact: true }).click()
  await expect(page.getByRole('switch', { name: 'Demo person', exact: true })).toHaveAttribute(
    'aria-checked',
    'false',
  )
  expect(await page.evaluate(() => localStorage.getItem('lodestar.token'))).toBe(own)
})
