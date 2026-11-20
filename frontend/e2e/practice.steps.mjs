import assert from 'node:assert/strict'
import { Given, Then, When } from '@cucumber/cucumber'
import { expect } from '@playwright/test'
import { origin } from './browser.mjs'

const stat = (page, label) => page.locator(`[data-stat="${label}"] .practice-stat-value`)
const number = locator => locator.textContent().then(Number.parseFloat)

Given('I start an individual practice test', async function () {
  const loaded = this.page.waitForResponse(response =>
    new URL(response.url()).pathname === '/api/v1/texts/random' && response.ok())
  await this.page.getByRole('link', { name: 'Start a practice test' }).click()
  await this.page.getByRole('button', { name: 'Español' }).click()
  await expect(this.page.getByRole('button', { name: 'Español' })).toHaveAttribute('aria-pressed', 'true')
  await this.page.getByRole('button', { name: 'Start test' }).click()
  this.text = (await (await loaded).json()).content
  this.input = this.page.getByRole('textbox', { name: 'Type the text' })
  await expect(this.input).toBeFocused()
  // Before any typing the panel shows its initial values: no speed, full accuracy.
  await expect(stat(this.page, 'Accuracy')).toHaveText('100%')
  assert.equal(await number(stat(this.page, 'PPM')), 0)
  this.character = index => this.page.locator(`[data-index="${index}"]`)
})

When('I type a {word} character at the current position', async function (kind) {
  const expected = this.text[0]
  await this.input.pressSequentially(kind === 'correct' ? expected : (expected === 'z' ? 'y' : 'z'))
})

Then('that character is marked {word}', async function (state) {
  await expect(this.character(0)).toHaveAttribute('data-state', state)
  await expect(this.character(1)).toHaveAttribute('data-state', 'pending')
})

Then('the live speed and accuracy reflect the {word} input', async function (kind) {
  // The live panel refreshes once per second while the test is running.
  if (kind === 'correct') {
    await expect.poll(() => number(stat(this.page, 'PPM'))).toBeGreaterThan(0)
    await expect(stat(this.page, 'Accuracy')).toHaveText('100%')
  } else {
    await expect(stat(this.page, 'Accuracy')).toHaveText('0%')
    // Checked only after the panel refreshed, so it is not the initial value.
    assert.equal(await number(stat(this.page, 'PPM')), 0)
  }
})

When('I type the whole practice text correctly', async function () {
  await this.input.pressSequentially(this.text)
})

Then('the results show speed, accuracy and score', async function () {
  await expect(this.page.getByRole('heading', { name: 'Your results' })).toBeVisible()
  await expect.poll(() => number(stat(this.page, 'PPM'))).toBeGreaterThan(0)
  await expect(stat(this.page, 'Accuracy')).toHaveText('100%')
  await expect.poll(() => number(stat(this.page, 'Score'))).toBeGreaterThan(0)
  this.result = {
    ppm: await stat(this.page, 'PPM').textContent(),
    accuracy: await stat(this.page, 'Accuracy').textContent(),
    score: await stat(this.page, 'Score').textContent(),
  }
})

Then('the match is saved in my history', async function () {
  await expect(this.page.getByRole('status').filter({ hasText: 'Match saved in your history.' })).toBeVisible()
  await this.page.goto(`${origin}/practice/history`)
  const rows = this.page.getByRole('region', { name: 'Saved practice tests' }).getByRole('row')
  await expect(rows).toHaveCount(2) // header row plus the match just saved
  const row = rows.nth(1)
  await expect(row.locator('.records-speed strong')).toHaveText(this.result.ppm)
  await expect(row.getByRole('cell').nth(2)).toHaveText(this.result.accuracy)
  await expect(row.locator('.records-score')).toHaveText(this.result.score)
})
