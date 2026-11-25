import assert from 'node:assert/strict'
import { randomBytes } from 'node:crypto'
import { Given, Then } from '@cucumber/cucumber'
import { expect } from '@playwright/test'
import { origin } from './browser.mjs'

const api = `${origin}/api/v1`
const practiceMatches = `${api}/matches/practice`
const englishText = 'The green bicycle crossed the quiet stone bridge before sunrise.'

Given('a fresh solo practice session at {int} by {int}', async function (width, height) {
  assert.match(process.env.TYPR_BROWSER_FIXTURE_DB ?? '', /^typr-registration-.+-db$/)
  await this.page.setViewportSize({ width, height })
  for (const role of ['seed', 'solo']) {
    const username = `${role}_${randomBytes(6).toString('hex')}`
    const data = { username, email: `${username}@example.com`, password: 'LocalTest123!' }
    assert.equal((await this.request.post(`${api}/auth/register`, { data })).status(), 201)
    const login = await this.request.post(`${api}/auth/login`, { data })
    assert.equal(login.status(), 200)
    const { token, user } = await login.json()
    const auth = { headers: { Authorization: `Bearer ${token}` } }
    if (role === 'seed') {
      const saved = await this.request.post(practiceMatches, {
        ...auth,
        data: {
          difficulty: 'medium', text: { content: englishText, language: 'eng' },
          typed: englishText, timeMs: 12000, keystrokes: englishText.length, errors: 0,
        },
      })
      assert.equal(saved.status(), 201)
    } else {
      this.practiceAuth = auth
      await this.page.addInitScript(([token, user]) => {
        localStorage.setItem('token', token)
        localStorage.setItem('user', JSON.stringify(user))
      }, [token, user])
    }
  }
  await this.page.goto(`${origin}/practice`)
})

Then('changing solo practice settings protects only the in-progress attempt', async function () {
  const { page } = this
  const start = page.getByRole('button', { name: 'Start test' })
  const input = page.getByRole('textbox', { name: 'Type the text' })
  const change = page.getByRole('button', { name: 'Change settings', exact: true })
  const dialog = page.getByRole('dialog', { name: 'Discard this attempt?' })
  const keep = dialog.getByRole('button', { name: 'Keep typing' })
  const discard = dialog.getByRole('button', { name: 'Discard and change settings' })
  const spanish = page.getByRole('button', { name: 'Español', exact: true })
  const easy = page.getByRole('button', { name: 'Easy 20 words' })
  const english = page.getByRole('button', { name: 'English', exact: true })
  const medium = page.getByRole('button', { name: 'Medium 30 words' })
  let submissions = 0
  page.on('request', request => {
    if (request.url() === practiceMatches && request.method() === 'POST') submissions++
  })

  await start.click()
  await expect(input).toBeFocused()
  await change.click()
  await expect(start).toBeVisible()
  await expect(dialog).toBeHidden()

  await start.click()
  await input.pressSequentially('A qui')
  await input.press('Escape')
  await change.click()
  await expect(dialog).toBeVisible()
  await expect(dialog).toHaveAccessibleDescription(/without saving it/)
  await expect(keep).toBeFocused()
  await keep.click()
  await expect(change).toBeFocused()
  await expect(input).toHaveValue('A qui')
  await expect(page.getByText(/^Español · Easy ·/)).toBeVisible()
  await input.press('e')
  await expect(input).toHaveValue('A quie')
  for (const _ of 'A quie') await input.press('Backspace')
  await expect(input).toHaveValue('')
  await input.press('Escape')
  await change.click()
  await expect(keep).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()
  await expect(change).toBeFocused()
  await expect(input).toHaveValue('')

  await input.press('A')
  await input.press('Escape')
  await change.click()
  await discard.click()
  await expect(start).toBeVisible()
  await expect(dialog).toBeHidden()
  await expect(spanish).toHaveAttribute('aria-pressed', 'true')
  await expect(easy).toHaveAttribute('aria-pressed', 'true')
  const afterDiscard = await this.request.get(practiceMatches, this.practiceAuth)
  assert.equal(afterDiscard.status(), 200)
  assert.deepEqual(await afterDiscard.json(), [])
  assert.equal(submissions, 0)

  await english.click()
  await medium.click()
  await start.click()
  await expect(input).toBeFocused()
  await expect(input).toHaveValue('')
  await expect(page.getByText(/^English · Medium ·/)).toBeVisible()
  await input.pressSequentially(englishText)
  await expect(page.getByRole('status').filter({ hasText: 'Match saved in your history.' })).toBeVisible()
  await change.click()
  await expect(start).toBeVisible()
  await expect(dialog).toBeHidden()
  await expect(english).toHaveAttribute('aria-pressed', 'true')
  await expect(medium).toHaveAttribute('aria-pressed', 'true')
  assert.equal(submissions, 1)
  const afterFinish = await this.request.get(practiceMatches, this.practiceAuth)
  assert.equal(afterFinish.status(), 200)
  const history = await afterFinish.json()
  assert.deepEqual(history.map(({ language, difficulty }) => [language, difficulty]), [['eng', 'medium']])
  await expect(page).toHaveURL(`${origin}/practice`)
})
