import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { randomBytes } from 'node:crypto'
import { Given, Then, When } from '@cucumber/cucumber'
import { expect } from '@playwright/test'
import { disconnected, httpError, origin } from './browser.mjs'
const invalid = 'Tu sesión ya no es válida. Inicia sesión de nuevo'
const credentials = (page) => page.evaluate(() => [localStorage.token, localStorage.user].map(value => value ?? null))
const profile = async (page, account) => {
  await expect(page).toHaveURL(/\/profile$/)
  await expect(page.getByRole('heading', { name: `Welcome back, ${account.username}` })).toBeVisible()
}
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
  await profile(this.page, this.account)
  this.credentials = await credentials(this.page)
  assert.ok(this.credentials.every(Boolean))
})

Then('the profile routes respect session state and replace redirect history', async function () {
  const { context } = await this.newContext()
  const guest = await context.newPage()
  await guest.goto(origin)
  await expect(guest.getByRole('heading', { name: /Type fast/ })).toBeVisible()
  await expect(guest).toHaveURL(`${origin}/`)
  for (const path of ['/profile', '/dashboard']) {
    await guest.goto(`${origin}${path}`)
    await loginScreen(guest)
  }

  await this.page.addInitScript(() => {
    if (!['/', '/dashboard'].includes(location.pathname)) return
    const fetch = window.fetch
    const held = new Promise(resolve => { window.releaseProfileValidation = resolve })
    window.fetch = async (url, options) => {
      if (url === '/api/v1/users/me') await held
      return fetch(url, options)
    }
  })

  for (const path of ['/', '/dashboard']) {
    await this.page.goto(`${origin}/about`)
    await this.page.goto(`${origin}${path}`)
    await expect(this.page.locator('main').getByRole('status')).toHaveText('Loading…')
    await expect(this.page).toHaveURL(`${origin}${path}`)
    await expect(this.page.locator('main h1')).toHaveCount(0)
    await this.page.evaluate(() => window.releaseProfileValidation())
    await profile(this.page, this.account)
    await this.page.goBack()
    await expect(this.page).toHaveURL(`${origin}/about`)
    await this.page.getByRole('link', { name: 'Profile', exact: true }).click()
    await profile(this.page, this.account)
  }

  const database = process.env.TYPR_BROWSER_FIXTURE_DB
  assert.match(database ?? '', /^typr-registration-[\da-f-]{36}-db$/)
  const { jti: sid } = JSON.parse(Buffer.from(this.credentials[0].split('.')[1], 'base64url'))
  assert.match(sid, /^[\da-f-]{36}$/)
  const result = execFileSync('docker', [
    'exec', '-i', database, 'psql', '-X', '-U', 'typr_test', '-d', 'typr_registration_test',
    '-v', 'ON_ERROR_STOP=1', '-v', `sid=${sid}`,
  ], {
    input: "UPDATE auth_sessions SET idle_expires_at = now() - interval '1 minute' WHERE id = :'sid';\n",
    encoding: 'utf8',
    timeout: 5_000,
  })
  assert.equal(result.trim(), 'UPDATE 1')

  for (const path of ['/', '/profile', '/dashboard']) {
    await this.page.evaluate(([token, user]) => Object.assign(localStorage, { token, user }), this.credentials)
    this.expectResourceError('/api/v1/users/me', httpError(401))
    const validation = this.page.waitForResponse(response => response.url().endsWith('/users/me'))
    await this.page.goto(`${origin}${path}`)
    await this.page.evaluate(() => window.releaseProfileValidation?.())
    assert.equal((await validation).status(), 401)
    await loginScreen(this.page, invalid)
    assert.deepEqual(await credentials(this.page), [null, null])
  }
})

When('I reload the profile and the API validates my session', async function () {
  const validation = this.page.waitForResponse(response => response.url().endsWith('/users/me') && response.ok())
  await this.page.reload()
  assert.equal((await validation).status(), 200)
  await profile(this.page, this.account)
  assert.deepEqual(await credentials(this.page), this.credentials)
})

When('I sign out with another tab open and a separate session for my account', async function () {
  this.tab = await this.page.context().newPage()
  await this.tab.goto(`${origin}/profile`)
  await profile(this.tab, this.account)
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
  await profile(this.tab, this.account)
  await this.tab.getByRole('button', { name: 'Practice', exact: true }).click()
  this.expectResourceError('/api/v1/matches/practice?offset=0&limit=11', httpError(401))
  await this.tab.getByRole('link', { name: 'History', exact: true }).click()
  await loginScreen(this.tab, invalid)
  await this.tab.evaluate(([token, user]) => Object.assign(localStorage, { token, user }), this.credentials)
  this.expectResourceError('/api/v1/users/me', httpError(401))
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
  await profile(this.page, this.account)
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
  this.expectResourceError('/api/v1/auth/logout', disconnected)
  await this.logoutRoute.abort('internetdisconnected')
  await loginScreen(this.page, 'Signed out on this device. Server revocation could not be confirmed.')
  await checkSession(this.request, this.credentials[0], 200)
})

When('I reload with a {word} validation failure', async function (failure) {
  this.expectResourceError('/api/v1/users/me', failure === '503' ? httpError(503) : disconnected)
  await this.page.route('**/api/v1/users/me', route => failure === '503' ? route.fulfill({ status: 503 }) : route.abort('internetdisconnected'))
  await this.page.reload()
})

Then('my credentials are retained and the profile stays hidden until retry succeeds', async function () {
  await expect(this.page.getByRole('alert')).toHaveText('Could not verify your session. Please try again.')
  await expect(this.page.getByRole('heading', { name: `Welcome back, ${this.account.username}` })).toHaveCount(0)
  assert.deepEqual(await credentials(this.page), this.credentials)
  await this.page.unroute('**/api/v1/users/me')
  await this.page.getByRole('button', { name: 'Retry' }).click()
  await profile(this.page, this.account)
})

Given('my browser session has {string}', async function (condition) {
  await checkSession(this.request, this.credentials[0], 200)
  this.rejectedToken = this.credentials[0]
  if (condition === 'an invalid token signature') {
    const [header, payload, signature] = this.rejectedToken.split('.')
    assert.ok(header && payload && signature, 'Expected a fixture JWT')
    this.rejectedToken = `${header}.${payload}.${signature[0] === 'A' ? 'B' : 'A'}${signature.slice(1)}`
    await this.page.evaluate(token => localStorage.setItem('token', token), this.rejectedToken)
  } else {
    assert.equal(condition, 'a deleted account')
    const database = process.env.TYPR_BROWSER_FIXTURE_DB
    assert.match(database ?? '', /^typr-registration-[\da-f-]{36}-db$/)
    assert.match(this.account.email, /^qa_[\da-f]{12}@example\.com$/)
    const result = execFileSync('docker', [
      'exec', '-i', database, 'psql', '-X', '-U', 'typr_test', '-d', 'typr_registration_test',
      '-v', 'ON_ERROR_STOP=1', '-v', `email=${this.account.email}`,
    ], {
      input: "DELETE FROM users WHERE email = :'email';\n",
      encoding: 'utf8',
      timeout: 5_000,
    })
    assert.equal(result.trim(), 'DELETE 1')
  }
  const [token, user] = await credentials(this.page)
  assert.ok(token === this.rejectedToken && user === this.credentials[1], 'Expected both stale local credentials')
})

When('I reload the profile with the rejected credentials', async function () {
  const path = '/api/v1/users/me'
  this.expectResourceError(path, httpError(401))
  await this.page.addInitScript(name => {
    window.ri14PrivateHeadingRendered = false
    new MutationObserver(() => {
      if ([...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].some(heading => heading.textContent === name)) {
        window.ri14PrivateHeadingRendered = true
      }
    }).observe(document, { childList: true, subtree: true, characterData: true })
  }, `Welcome back, ${this.account.username}`)
  const [response] = await Promise.all([
    this.page.waitForResponse(response => response.url() === `${origin}${path}` &&
      response.request().method() === 'GET'),
    this.page.reload(),
  ])
  this.rejectedResponse = response
})

Then('the API rejects the session and the browser signs out without displaying private data', async function () {
  assert.ok(this.rejectedResponse.request().headers().authorization === `Bearer ${this.rejectedToken}`,
    'The browser must send the intended stale credential')
  assert.equal(this.rejectedResponse.status(), 401)
  assert.equal(this.rejectedResponse.headers()['www-authenticate'], 'Bearer')
  await loginScreen(this.page, invalid)
  assert.deepEqual(await credentials(this.page), [null, null])
  await expect(this.page.getByRole('heading', { name: `Welcome back, ${this.account.username}` })).toHaveCount(0)
  assert.equal(await this.page.evaluate(() => window.ri14PrivateHeadingRendered), false)
})
