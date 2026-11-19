import assert from 'node:assert/strict'
import { randomBytes } from 'node:crypto'
import { Given, Then, When } from '@cucumber/cucumber'
import { expect } from '@playwright/test'

const origin = 'http://127.0.0.1:5173'
const api = `${origin}/api/v1`
const auth = token => ({ headers: { Authorization: `Bearer ${token}` } })
const warning = 'Your session expires in 5 minutes or less.'
const input = page => page.getByRole('textbox', { name: 'Type the text' })

async function positionClock(world) {
  const token = world.credentials[0]
  const { exp } = JSON.parse(Buffer.from(token.split('.')[1], 'base64url').toString())
  const beforeWarning = exp * 1000 - 300_001
  await world.page.clock.install({ time: beforeWarning - 1000 })
  await world.page.clock.pauseAt(beforeWarning)
}

Given('I start an active practice attempt near absolute expiry', async function () {
  await positionClock(this)
  this.submissions = 0
  this.page.on('request', request => {
    if (request.method() === 'POST' && request.url() === `${api}/matches/practice`) this.submissions++
  })
  await this.page.getByRole('link', { name: 'Start a practice test' }).click()
  await this.page.getByRole('button', { name: 'Start test' }).click()
  await input(this.page).press('A')
  await expect(this.page.locator('.practice--focus')).toBeVisible()
})

Given('I enter an active race with a separate peer near absolute expiry', async function () {
  const id = randomBytes(6).toString('hex')
  const peerAccount = { username: `peer_${id}`, email: `peer_${id}@example.com`, password: 'LocalTest123!' }
  const peerContext = await this.browser.newContext()
  this.peer = await peerContext.newPage()
  assert.equal((await this.request.post(`${api}/auth/register`, { data: peerAccount })).status(), 201)
  const login = await this.request.post(`${api}/auth/login`, { data: peerAccount })
  assert.equal(login.status(), 200)
  const { token, user } = await login.json()
  await peerContext.addInitScript(([token, user]) => {
    localStorage.setItem('token', token)
    localStorage.setItem('user', JSON.stringify(user))
  }, [token, user])
  const room = await this.request.post(`${api}/rooms`, {
    ...auth(this.credentials[0]), data: { language: 'spa', difficulty: 'easy', timeLimitS: 60 },
  })
  assert.equal(room.status(), 201)
  const { code } = await room.json()
  assert.equal((await this.request.post(`${api}/rooms/${code}/join`, auth(token))).status(), 200)
  await positionClock(this)
  await this.page.goto(`${origin}/rooms/${code}`)
  await this.peer.goto(`${origin}/rooms/${code}`)
  await this.peer.getByRole('button', { name: 'I am ready' }).click()
  await this.page.getByRole('button', { name: 'Start race' }).click()
  await expect(input(this.page)).toBeFocused({ timeout: 10_000 })
  await this.page.getByRole('button', { name: 'Focus', exact: true }).click()
  await expect(this.page.locator('.practice--focus')).toBeVisible()
})

When('I cross the five-minute boundary offline', async function () {
  await this.page.context().setOffline(true)
  await expect(this.page.getByText(warning, { exact: true })).toHaveCount(0)
  await this.page.clock.runFor(1)
})

Then('I see an expiry warning without losing typing focus', async function () {
  await expect(this.page.getByRole('status').filter({ hasText: warning })).toBeVisible()
  await expect(input(this.page)).toBeFocused()
  await expect(this.page.locator('.practice--focus')).toBeVisible()
})

When('the browser reaches the absolute deadline', async function () {
  await this.page.clock.fastForward(299_999)
  await expect(input(this.page)).toBeFocused()
  await this.page.clock.runFor(1)
})

When('the server revokes my racing session', async function () {
  await this.page.context().setOffline(false)
  const response = await this.request.post(`${api}/auth/logout`, auth(this.credentials[0]))
  assert.equal(response.status(), 204)
})

Then('I am signed out with the notice {string}', async function (notice) {
  await expect(this.page).toHaveURL(/\/login$/, { timeout: 10_000 })
  await expect(this.page.getByRole('alert')).toHaveText(notice)
  await expect(input(this.page)).toHaveCount(0)
  assert.deepEqual(await this.page.evaluate(() => [localStorage.token, localStorage.user]), [undefined, undefined])
})

Then('no practice attempt was submitted', function () {
  assert.equal(this.submissions, 0)
})

Then('the peer can finish the race', async function () {
  await expect(input(this.peer)).toBeFocused()
  const phrase = await this.peer.locator('#practice-text').textContent()
  await input(this.peer).pressSequentially(phrase)
  await expect(this.peer.getByRole('heading', { name: 'Final results' })).toBeVisible()
})

Then('signing in again does not resume play', async function () {
  await this.page.context().setOffline(false)
  await this.registration.email.fill(this.account.email)
  await this.registration.password.fill(this.account.password)
  await this.registration.form.getByRole('button', { name: 'Sign in' }).click()
  await expect(this.page).toHaveURL(/\/dashboard$/)
  await expect(input(this.page)).toHaveCount(0)
})
