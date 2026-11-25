import assert from 'node:assert/strict'
import { randomBytes } from 'node:crypto'
import { performance } from 'node:perf_hooks'
import { Given, Then, When } from '@cucumber/cucumber'
import { expect } from '@playwright/test'
import { origin } from './browser.mjs'

const api = `${origin}/api/v1`
const auth = token => ({ headers: { Authorization: `Bearer ${token}` } })

function recordRaceFrames(page) {
  const frames = []
  page.on('websocket', socket => {
    socket.on('framereceived', ({ payload }) => {
      const at = performance.now()
      const message = JSON.parse(payload.toString())
      if (['countdown', 'race_start'].includes(message.type)) frames.push({ at, message })
    })
  })
  return frames
}

Given('two players are ready to start a race in separate browser contexts', async function () {
  const name = `peer_${randomBytes(6).toString('hex')}`
  const account = { username: name, email: `${name}@example.com`, password: 'LocalTest123!' }
  const { context } = await this.newContext()
  const peer = await context.newPage()
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
  this.players = [this.page, peer].map(page => ({ page, frames: recordRaceFrames(page) }))
  await Promise.all(this.players.map(({ page }) => page.goto(`${origin}/rooms/${code}`)))
  await peer.getByRole('button', { name: 'I am ready' }).click()
})

When('the host starts the race', async function () {
  await Promise.all(this.players.map(({ page }) => page.evaluate(() => {
    const ticks = []
    window.raceStartObservation = { ticks, textDuringCountdown: false }
    const observer = new MutationObserver(() => {
      const tick = document.querySelector('.race-countdown-number')
      const text = document.querySelector('#practice-text')
      if (tick?.checkVisibility({ visibilityProperty: true })) {
        if (ticks.at(-1) !== tick.textContent) ticks.push(tick.textContent)
        if (text) window.raceStartObservation.textDuringCountdown = true
      }
      if (text && !tick) observer.disconnect()
    })
    observer.observe(document.body, { childList: true, subtree: true, characterData: true })
  })))
  await this.page.getByRole('button', { name: 'Start race' }).click()
})

Then('both players see a three-second countdown followed by the same race text', async function () {
  const evidence = await Promise.all(this.players.map(async ({ page, frames }) => {
    const text = page.locator('#practice-text')
    await expect(text).toBeVisible({ timeout: 8_000 })
    await expect.poll(() => frames.length).toBeGreaterThanOrEqual(2)
    const [countdown, start] = frames
    return {
      types: frames.map(({ message }) => message.type),
      seconds: countdown.message.seconds,
      elapsedMs: start.at - countdown.at,
      startAt: start.at,
      payloadText: start.message.text?.content,
      renderedText: await text.textContent(),
      ...await page.evaluate(() => window.raceStartObservation),
    }
  }))
  const [host, peer] = evidence
  this.log(`Race start evidence: ${JSON.stringify({
    countdownMs: evidence.map(player => Number(player.elapsedMs.toFixed(3))),
    ticks: evidence.map(player => player.ticks),
    startReceiptSkewMs: Number(Math.abs(host.startAt - peer.startAt).toFixed(3)),
  })}`)
  for (const player of evidence) {
    assert.deepEqual(player.types, ['countdown', 'race_start'])
    assert.deepEqual(player.ticks, ['3', '2', '1'])
    assert.equal(player.textDuringCountdown, false)
    assert.equal(player.seconds, 3)
    // Compare at the requirement's whole-second precision, not exact milliseconds.
    assert.equal(Math.round(player.elapsedMs / 1000), 3)
    assert.ok(player.payloadText?.trim())
    assert.equal(player.renderedText, player.payloadText)
  }
  assert.equal(host.renderedText, peer.renderedText)
})
