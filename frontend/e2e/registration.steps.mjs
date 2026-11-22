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

Given('I open the registration form', async function () {
  await this.registration.open(origin)
})

When('I enter a {word} of {int} characters and submit valid remaining fields', async function (field, length) {
  const id = randomBytes(6).toString('hex')
  this.values = { username: `qa_${id}`, email: `qa_${id}@example.com`, password: 'LocalTest123!' }
  this.values[field] = this.values[field].padEnd(length, 'x').slice(0, length)
  const invalid = field === 'username' ? length < 3 || length > 20 : length < 8
  if (invalid) {
    this.expectResourceError('/api/v1/auth/register', httpError(422))
  }
  this.registrationStatus = await this.registration.submit(this.values)
  if (invalid) assert.equal(this.registrationStatus, 422)
})

Then('registration creates an account and opens the profile', async function () {
  assert.equal(this.registrationStatus, 201)
  await this.registration.expectProfile()
})

Then('the {word} field displays a length message mentioning {int} characters', async function (field, limit) {
  await this.registration.expectLengthError(field, limit)
})
