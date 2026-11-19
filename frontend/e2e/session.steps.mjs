import assert from 'node:assert/strict'
import { randomBytes } from 'node:crypto'
import { Given, Then, When } from '@cucumber/cucumber'
import { expect } from '@playwright/test'

const origin = 'http://127.0.0.1:5173'
const invalid = 'Tu sesión ya no es válida. Inicia sesión de nuevo'
const credentials = (page) => page.evaluate(() => [localStorage.token, localStorage.user].map(value => value ?? null))
const dashboard = (page, account) => expect(page.getByRole('heading', { name: `Welcome back, ${account.username}` })).toBeVisible()
const signOut = async (page, account) => {
  await page.getByRole('button', { name: account.username }).click()
  await page.getByRole('button', { name: 'Sign out' }).click()
}
const loginScreen = async (page, notice) => {
  await expect(page).toHaveURL(/\/login$/)
  await expect(page.getByRole('heading', { name: 'Welcome back!' })).toBeVisible()
  if (notice) await expect(page.getByRole('alert')).toHaveText(notice)
  else await expect(page.getByText(invalid, { exact: true })).toHaveCount(0)
}
const checkSession = async (request, token, status) => {
  const response = await request.get(`${origin}/api/v1/users/me`, { headers: { Authorization: `Bearer ${token}` } })
  assert.equal(response.status(), status)
}

Given('I register a new account in the browser', async function () {
  const id = randomBytes(6).toString('hex')
  this.account = { username: `qa_${id}`, email: `qa_${id}@example.com`, password: 'LocalTest123!' }
  this.page = this.registration.page
  await this.registration.open(origin)
  assert.equal(await this.registration.submit(this.account), 201)
  await dashboard(this.page, this.account)
  this.credentials = await credentials(this.page)
  assert.ok(this.credentials.every(Boolean))
})

When('I reload the dashboard and the API validates my session', async function () {
  const validation = this.page.waitForResponse(response => response.url().endsWith('/users/me') && response.ok())
  await this.page.reload()
  assert.equal((await validation).status(), 200)
  await dashboard(this.page, this.account)
  assert.deepEqual(await credentials(this.page), this.credentials)
})

When('I sign out with another tab open and a separate session for my account', async function () {
  this.tab = await this.page.context().newPage()
  await this.tab.goto(`${origin}/dashboard`)
  await dashboard(this.tab, this.account)
  const response = await this.request.post(`${origin}/api/v1/auth/login`, { data: this.account })
  assert.equal(response.status(), 200)
  this.otherToken = (await response.json()).token
  assert.notEqual(this.otherToken, this.credentials[0])
  const unauthorized = await this.request.post(`${origin}/api/v1/auth/logout`)
  assert.equal(unauthorized.status(), 401)
  await this.page.getByRole('link', { name: 'Start a practice test' }).click()
  const revoked = this.page.waitForResponse(response => response.url().endsWith('/auth/logout'))
  await signOut(this.page, this.account)
  assert.equal((await revoked).status(), 204)
  await loginScreen(this.page)
  assert.deepEqual(await credentials(this.page), [null, null])
})

Then('only the browser session is revoked', async function () {
  await checkSession(this.request, this.credentials[0], 401)
  await checkSession(this.request, this.otherToken, 200)
})

Then('the other tab detects the revocation on a protected request and on reload', async function () {
  await dashboard(this.tab, this.account)
  await this.tab.getByRole('button', { name: 'Practice', exact: true }).click()
  await this.tab.getByRole('link', { name: 'History', exact: true }).click()
  await loginScreen(this.tab, invalid)
  await this.tab.evaluate(([token, user]) => Object.assign(localStorage, { token, user }), this.credentials)
  await this.tab.reload()
  await loginScreen(this.tab, invalid)
  assert.deepEqual(await credentials(this.tab), [null, null])
})

Then('I can go Back without seeing private data and sign in with a new session', async function () {
  await this.page.goBack()
  await loginScreen(this.page)
  await this.registration.email.fill(this.account.email)
  await this.registration.password.fill(this.account.password)
  await this.registration.form.getByRole('button', { name: 'Sign in' }).click()
  await dashboard(this.page, this.account)
  const [token] = await credentials(this.page)
  assert.notEqual(token, this.credentials[0])
  await checkSession(this.request, token, 200)
})

When('my logout request loses connectivity', async function () {
  await this.page.route('**/api/v1/auth/logout', route => { this.logoutRoute = route })
  await signOut(this.page, this.account)
})

Then('local sign-out finishes first and warns if revocation cannot be confirmed', async function () {
  await loginScreen(this.page)
  assert.deepEqual(await credentials(this.page), [null, null])
  await expect.poll(() => Boolean(this.logoutRoute)).toBe(true)
  await this.logoutRoute.abort('internetdisconnected')
  await loginScreen(this.page, 'Signed out on this device. Server revocation could not be confirmed.')
  await checkSession(this.request, this.credentials[0], 200)
})

When('I reload with a {word} validation failure', async function (failure) {
  await this.page.route('**/api/v1/users/me', route => failure === '503' ? route.fulfill({ status: 503 }) : route.abort('internetdisconnected'))
  await this.page.reload()
})

Then('my credentials are retained and the dashboard stays hidden until retry succeeds', async function () {
  await expect(this.page.getByRole('alert')).toHaveText('Could not verify your session. Please try again.')
  await expect(this.page.getByRole('heading', { name: `Welcome back, ${this.account.username}` })).toHaveCount(0)
  assert.deepEqual(await credentials(this.page), this.credentials)
  await this.page.unroute('**/api/v1/users/me')
  await this.page.getByRole('button', { name: 'Retry' }).click()
  await dashboard(this.page, this.account)
})
