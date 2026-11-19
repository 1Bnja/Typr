import assert from 'node:assert/strict'
import { randomBytes } from 'node:crypto'
import { Given, Then, When } from '@cucumber/cucumber'
import { httpError, origin } from './browser.mjs'

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
