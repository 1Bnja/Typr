import assert from 'node:assert/strict'
import { randomBytes } from 'node:crypto'
import { Given, Then, When } from '@cucumber/cucumber'
import { expect } from '@playwright/test'
import { origin } from './browser.mjs'

const api = `${origin}/api/v1`
const path = '/practice/leaderboard'
const table = page => page.getByRole('table', { name: /Best completed test for each typist/ })
const monthOf = date => new Intl.DateTimeFormat('en-CA', {
  timeZone: 'America/Santiago', year: 'numeric', month: '2-digit',
}).format(date)
const seed = async (world, username, difficulty, language, content) => {
  const account = { username, email: `${username}@example.com`, password: `Qa!${randomBytes(12).toString('hex')}` }
  const registered = await world.request.post(`${api}/auth/register`, { data: account })
  assert.equal(registered.status(), 201, `Register fixture ${username}`)
  const login = await world.request.post(`${api}/auth/login`, { data: account })
  assert.equal(login.status(), 200, `Authenticate fixture ${username}`)
  const { token } = await login.json()
  const saved = await world.request.post(`${api}/matches/practice`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { difficulty, text: { content, language }, typed: content, timeMs: 12000, keystrokes: content.length, errors: 0 },
  })
  assert.equal(saved.status(), 201, `Save fixture ${username}`)
  const result = await saved.json()
  assert.deepEqual([result.difficulty, result.language, result.progress, result.precisionPct], [difficulty, language, 1, 100])
  const date = new Date(result.finishedAt)
  if (world.seedDate) assert.equal(monthOf(date), monthOf(world.seedDate), 'Fixture results must share a Santiago month')
  world.seedDate = date
}

Given('distinct practice results for Easy Spanish, Medium Spanish and Medium English', async function () {
  // Text content is globally unique in PostgreSQL, even across difficulties.
  await seed(this, 'rank_easy_es', 'easy', 'spa', 'La práctica diaria mejora la velocidad al escribir con cuidado.')
  await seed(this, 'rank_medium_es', 'medium', 'spa', 'Los pájaros vuelan sobre el valle mientras amanece en la montaña.')
  await seed(this, 'rank_medium_en', 'medium', 'eng', 'Daily typing practice improves both speed and accuracy.')
})

Given('a completed Hard Spanish result but no Hard English result', async function () {
  await seed(this, 'rank_hard_es', 'advanced', 'spa', 'Las corrientes marinas transportan nutrientes por regiones de temperatura variable.')
})

When('I open the monthly ranking for the seeded month', async function () {
  await this.page.clock.setFixedTime(this.seedDate)
  await this.page.goto(`${origin}${path}`)
  await expect(this.page.getByRole('heading', { name: 'Monthly leaderboard' })).toBeVisible()
  this.documentMarker = randomBytes(16).toString('hex')
  await this.page.evaluate(marker => { document.documentElement.dataset.qaRankingDocument = marker }, this.documentMarker)
  this.documentRequests = 0
  this.page.on('request', request => {
    if (request.resourceType() === 'document' && request.isNavigationRequest()) this.documentRequests++
  })
})

async function changeFilter(world, click, expected) {
  const pending = world.page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/v1/matches/leaderboard' &&
      url.searchParams.get('month') === monthOf(world.seedDate) &&
      Object.entries(expected).every(([key, value]) => url.searchParams.get(key) === value)
  })
  await click()
  const response = await pending
  assert.equal(response.status(), 200)
  world.filteredEntries = (await response.json()).entries.map(entry => entry.username)
}

When('I select the {string} ranking difficulty', async function (difficulty) {
  this.rankingDifficulty = { Medium: 'medium', Hard: 'advanced' }[difficulty]
  await changeFilter(this, () => this.page.getByRole('button', { name: difficulty, exact: true }).click(),
    { difficulty: this.rankingDifficulty, language: 'spa' })
})

When('I select the {string} ranking language', async function (language) {
  await this.page.getByRole('button', { name: /^Language / }).click()
  await changeFilter(this, () => this.page.getByRole('option', { name: language, exact: true }).click(),
    { difficulty: this.rankingDifficulty, language: 'eng' })
})

Then('only {string} appears in the ranking', async function (username) {
  if (this.filteredEntries) assert.deepEqual(this.filteredEntries, [username])
  const ranking = table(this.page)
  await expect(ranking).toBeVisible()
  await expect(ranking.getByRole('rowheader')).toHaveCount(1)
  await expect(ranking.getByRole('rowheader').locator('.records-username')).toHaveText(username)
  this.log(`Visible ranking: ${username}`)
})

Then('the ranking remains in the original document without a navigation request', async function () {
  await expect(this.page).toHaveURL(`${origin}${path}`)
  assert.equal(await this.page.evaluate(() => document.documentElement.dataset.qaRankingDocument), this.documentMarker)
  assert.equal(this.documentRequests, 0)
  this.log('Same document marker; 0 document navigation requests')
})

Then('the successful ranking response is empty and no table or error is displayed', async function () {
  assert.deepEqual(this.filteredEntries, [])
  await expect(this.page.locator('.records-content[aria-busy="false"]')).toBeVisible()
  await expect(table(this.page)).toHaveCount(0)
  await expect(this.page.getByRole('alert')).toHaveCount(0)
  this.log('HTTP 200; entries=[]; ranking settled; no table or alert')
})

Then('the empty ranking message is exactly {string}', async function (message) {
  const feedback = this.page.locator('.records-content .records-feedback')
  await expect(feedback).toBeVisible()
  const observed = await feedback.innerText()
  const lines = observed.split('\n').map(line => line.trim()).filter(Boolean)
  this.log(`Visible empty state: ${lines.join(' | ')}`)
  assert.ok(lines.includes(message), `Expected an exact visible line ${JSON.stringify(message)}, got ${JSON.stringify(lines)}`)
})
