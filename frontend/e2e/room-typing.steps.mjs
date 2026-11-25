import assert from 'node:assert/strict'
import { randomBytes } from 'node:crypto'
import { Given, Then, When } from '@cucumber/cucumber'
import { expect } from '@playwright/test'
import { origin } from './browser.mjs'

const api = `${origin}/api/v1`
const auth = token => ({ headers: { Authorization: `Bearer ${token}` } })
const input = page => page.getByRole('textbox', { name: 'Type the text' })
const instruction = page => page.locator('#race-instructions')
const firstCharacter = page => page.locator('#practice-text [data-index="0"]')
const caret = page => page.locator('.practice-caret').evaluate(element =>
  getComputedStyle(element).transform)
const background = locator => locator.evaluate(element => getComputedStyle(element).backgroundColor)

async function expectProgress(world, typed) {
  const percent = Math.round(100 * typed / world.text.length)
  await expect(world.page.locator('.practice-character-count')).toHaveText(
    `${typed} / ${world.text.length} characters`,
  )
  for (const page of [world.page, world.rival]) {
    const bar = page.getByRole('progressbar', { name: `${world.account.username} progress`, exact: true })
    await expect(bar).toHaveAttribute('aria-valuenow', String(percent))
    await expect(bar.locator('..').getByText(`${percent}%`, { exact: true })).toBeVisible()
  }
}

Given('I start a race with a rival in a separate browser context', async function () {
  const id = randomBytes(6).toString('hex')
  const account = { username: `rival_${id}`, email: `rival_${id}@example.com`, password: 'LocalTest123!' }
  const { context } = await this.newContext()
  this.rival = await context.newPage()
  await this.page.emulateMedia({ reducedMotion: 'reduce' })
  assert.equal((await this.request.post(`${api}/auth/register`, { data: account })).status(), 201)
  const login = await this.request.post(`${api}/auth/login`, { data: account })
  assert.equal(login.status(), 200)
  const { token, user } = await login.json()
  await context.addInitScript(([token, user]) => {
    localStorage.setItem('token', token)
    localStorage.setItem('user', JSON.stringify(user))
  }, [token, user])
  const room = await this.request.post(`${api}/rooms`, {
    ...auth(this.credentials[0]), data: { language: 'spa', difficulty: 'easy', timeLimitS: 60 },
  })
  assert.equal(room.status(), 201)
  const { code } = await room.json()
  assert.equal((await this.request.post(`${api}/rooms/${code}/join`, auth(token))).status(), 200)
  this.updates = []
  // The server broadcasts even an error-only update. Wait for that round trip
  // before checking the rival, rather than passing on the initial 0% render.
  this.rival.on('websocket', socket => {
    socket.on('framereceived', ({ payload }) => {
      const message = JSON.parse(payload.toString())
      if (message.type === 'progress_update') this.updates.push(message.progress)
    })
  })
  await this.page.goto(`${origin}/rooms/${code}`)
  await this.rival.goto(`${origin}/rooms/${code}`)
  await this.rival.getByRole('button', { name: 'I am ready' }).click()
  await this.page.getByRole('button', { name: 'Start race' }).click()
  await expect(input(this.page)).toBeFocused({ timeout: 10_000 })
  await expect(input(this.rival)).toBeFocused()
  this.text = await this.page.locator('#practice-text').textContent()
  assert.ok(this.text && Math.round(100 / this.text.length) > 0, 'Fixture must show first-character progress')
  this.wrong = this.text[0] === 'x' ? 'z' : 'x'
  await expectProgress(this, 0)
  await expect(this.page.locator('.practice-text-window')).toHaveAttribute('data-ready', 'true')
  await expect(this.page.locator('.practice-caret')).toBeVisible()
  this.initialCaret = await caret(this.page)
  this.pendingBackground = await background(firstCharacter(this.page))
})

When('I type a wrong character', async function () {
  await input(this.page).pressSequentially(this.wrong)
})

async function expectBlocked(world) {
  await expect(instruction(world.page)).toHaveAttribute('data-blocked', 'true')
  await expect(input(world.page)).toHaveValue(world.wrong)
  const character = firstCharacter(world.page)
  await expect(character).toBeVisible()
  await expect(character).toHaveText(world.wrong)
  await expect(character).toHaveClass(/practice-character--incorrect/)
  assert.notEqual(await background(character), world.pendingBackground, 'Wrong input must have a visible highlight')
  await expectProgress(world, 0)
  assert.equal(await caret(world.page), world.initialCaret, 'A wrong character must not move the rendered caret')
}

Then('the wrong character is highlighted without moving my caret or increasing either progress display', async function () {
  await expect.poll(() => this.updates.slice()).toEqual([0])
  await expectBlocked(this)
})

When('I try the expected character before Backspace', async function () {
  await input(this.page).pressSequentially(this.text[0])
})

Then('the same mistake still blocks typing and progress', async function () {
  await expectBlocked(this)
})

When('I erase the mistake without typing a valid character', async function () {
  await input(this.page).press('Backspace')
})

Then('the block clears without increasing progress', async function () {
  await expect(instruction(this.page)).toHaveAttribute('data-blocked', 'false')
  await expect(input(this.page)).toHaveValue('')
  await expect(firstCharacter(this.page)).toHaveText(this.text[0])
  await expect(firstCharacter(this.page)).toHaveClass(/practice-character--pending/)
  await expectProgress(this, 0)
  this.correctedCaret = await caret(this.page)
})

When('I type the next valid character', async function () {
  await input(this.page).pressSequentially(this.text[0])
})

Then('both progress displays advance and my cursor advances only for valid input', async function () {
  await expect(input(this.page)).toHaveValue(this.text[0])
  await expect.poll(() => this.updates.slice()).toEqual([0, 1 / this.text.length])
  await expectProgress(this, 1)
  const advancedCaret = await caret(this.page)
  assert.notEqual(advancedCaret, this.initialCaret, 'Valid input must move the rendered caret')
  assert.equal(this.correctedCaret, this.initialCaret, 'Backspace must leave the caret at the original position')
})
