import assert from 'node:assert/strict'
import { randomBytes } from 'node:crypto'
import { Given, Then, When } from '@cucumber/cucumber'
import { httpError, origin } from './browser.mjs'

Given('I open the registration form with valid new account data', async function () {
  const id = randomBytes(6).toString('hex')
  this.account = { username: `qa_${id}`, email: `qa_${id}@example.com`, password: 'LocalTest123!' }
  await this.registration.open(origin)
})

When('I submit the registration form', async function () {
  this.status = await this.registration.submit(this.account)
})

Then('the account is created', async function () {
  assert.equal(this.status, 201)
})

Then('I land on the dashboard with an authenticated session', async function () {
  await this.registration.expectDashboard(this.account)
  const [token, user] = await this.page.evaluate(() => [localStorage.token, localStorage.user])
  assert.ok(token, 'A session token must be stored')
  assert.equal(JSON.parse(user).username, this.account.username)
  const profile = await this.request.get(`${origin}/api/v1/users/me`, { headers: { Authorization: `Bearer ${token}` } })
  assert.equal(profile.status(), 200)
  const me = await profile.json()
  assert.equal(me.username, this.account.username)
  assert.equal(me.email, this.account.email)
  assert.equal(me.id, JSON.parse(user).id)
})

Given('an account exists and I open the registration form', async function () {
  const id = randomBytes(6).toString('hex')
  this.account = { username: `qa_${id}`, email: `qa_${id}@example.com`, password: 'LocalTest123!' }
  const response = await this.request.post(`${origin}/api/v1/auth/register`, { data: this.account })
  assert.equal(response.status(), 201, 'The isolated API must create the fixture')
  await this.registration.open(origin)
})

When('I submit registration with a {word} conflict', async function (conflict) {
  this.values = {
    username: conflict === 'email' ? `${this.account.username}_new` : this.account.username,
    email: conflict === 'username' ? `other_${this.account.email}` : this.account.email,
    password: 'DifferentLocal123!',
  }
  this.expectResourceError('/api/v1/auth/register', httpError(409))
  assert.equal(await this.registration.submit(this.values), 409)
})

Then('the email field reports {string}', async function (message) {
  await this.registration.expectEmailError(message)
})

Then('the form reports {string} without marking email invalid', async function (message) {
  await this.registration.expectFormError(message)
})

Then('registration keeps all my entered values', async function () {
  await this.registration.expectValues(this.values)
})
