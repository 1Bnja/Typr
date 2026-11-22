import assert from 'node:assert/strict'
import { Given, Then, When } from '@cucumber/cucumber'
import { expect } from '@playwright/test'
import { origin } from './browser.mjs'

const table = page => page.getByRole('region', { name: 'Monthly practice ranking' })
const isRankingRequest = (request, key, value) => {
  const url = new URL(request.url())
  return url.pathname === '/api/v1/matches/leaderboard' && url.searchParams.get(key) === value
}

When('I open the monthly ranking', async function () {
  await expect(this.page.getByRole('status').filter({ hasText: 'Match saved in your history.' })).toBeVisible()
  await this.page.goto(`${origin}/practice/leaderboard`)
  await expect(table(this.page)).toBeVisible()
  // Survives client-side updates only: a full reload would clear it.
  await this.page.evaluate(() => { window.rankingPageLoaded = true })
})

Given('the ranking lists my result', async function () {
  await expect(table(this.page).getByText(this.account.username)).toBeVisible()
})

When('I switch the language filter to English', async function () {
  this.refreshed = this.page.waitForRequest(request => isRankingRequest(request, 'language', 'eng'))
  await this.page.getByRole('button', { name: /^Language/ }).click()
  await this.page.getByRole('option', { name: 'English' }).click()
})

Then('the table refreshes without reloading the page', async function () {
  await this.refreshed
  await expect(this.page.getByRole('heading', { name: 'The first place is still open.' })).toBeVisible()
  assert.equal(await this.page.evaluate(() => window.rankingPageLoaded), true, 'The page was reloaded')
})

Then('my result is no longer listed', async function () {
  await expect(table(this.page)).toHaveCount(0)
})

When('I switch the difficulty filter to Hard', async function () {
  this.refreshed = this.page.waitForRequest(request => isRankingRequest(request, 'difficulty', 'advanced'))
  await this.page.getByRole('button', { name: 'Hard' }).click()
  await this.refreshed
})

Then('the ranking says the first place is still open', async function () {
  await expect(this.page.getByRole('heading', { name: 'The first place is still open.' })).toBeVisible()
  await expect(this.page.getByText('No completed tests for this month and level yet.')).toBeVisible()
})
