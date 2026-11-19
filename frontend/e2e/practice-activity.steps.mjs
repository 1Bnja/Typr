import assert from 'node:assert/strict'
import { Then, When } from '@cucumber/cucumber'
import { expect } from '@playwright/test'

When('I start a practice test with a controlled clock', async function () {
  this.notices = []
  await this.page.clock.install()
  await this.page.route('**/api/v1/texts/random?*', route => route.fulfill({
    json: { id: 1, content: 'a phrase long enough to keep typing', language: 'spa', difficulty: 'easy' },
  }))
  await this.page.route('**/api/v1/auth/practice-activity', async route => {
    this.notices.push({ method: route.request().method(), body: route.request().postDataJSON() })
    await route.abort('internetdisconnected')
  })
  await this.page.getByRole('link', { name: 'Start a practice test' }).click()
  await this.page.getByRole('button', { name: 'Start test' }).click()
  this.input = this.page.getByRole('textbox', { name: 'Type the text' })
  await expect(this.input).toBeFocused()
  await this.page.clock.pauseAt(new Date(await this.page.evaluate(() => Date.now()) + 1000))
})

Then('advancing the clock without typing sends nothing', async function () {
  await this.input.evaluate(input => {
    input.value = 'x'
    input.dispatchEvent(new Event('input', { bubbles: true }))
    input.value = ''
  })
  await this.page.clock.fastForward(60_000)
  assert.deepEqual(this.notices, [])
})

Then('real typing sends a content-free notice and respects the minute boundary', async function () {
  await this.input.pressSequentially('ab')
  await expect.poll(() => this.notices.length).toBe(1)
  await this.page.clock.fastForward(59_999)
  await this.input.press('c')
  assert.equal(this.notices.length, 1)
  await this.page.clock.fastForward(1)
  assert.equal(this.notices.length, 1)
  await this.input.press('d')
  await expect.poll(() => this.notices.length).toBe(2)
  const [first, second] = this.notices
  for (const { method, body } of this.notices) {
    assert.equal(method, 'POST')
    assert.deepEqual(Object.keys(body), ['noticeId'])
    assert.ok(Number.isSafeInteger(body.noticeId))
  }
  assert.equal(second.body.noticeId - first.body.noticeId, 60_000)
})
