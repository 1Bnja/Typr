import assert from 'node:assert/strict'
import test from 'node:test'
import authService, { DuplicateEmailError, login, register } from '../src/features/auth/services/authService.js'

const account = { username: 'ana', email: 'ana@example.test', password: 'secret-pass-1' }
const reply = (status, body) => async () => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => {
    if (body === undefined) throw new SyntaxError('Unexpected end of JSON input')
    return body
  },
})

test('register posts the account as JSON and returns the created user', async (context) => {
  const created = { id: 1, username: 'ana', email: 'ana@example.test' }
  const fetchMock = context.mock.method(globalThis, 'fetch', reply(201, created))

  assert.deepEqual(await register(account), created)

  const [url, request] = fetchMock.mock.calls[0].arguments
  assert.equal(url, '/api/v1/auth/register')
  assert.equal(request.method, 'POST')
  assert.equal(request.headers['Content-Type'], 'application/json')
  assert.deepEqual(JSON.parse(request.body), account)
})

test('register maps a 409 duplicate email to DuplicateEmailError', async (context) => {
  context.mock.method(globalThis, 'fetch', reply(409, { detail: 'Este correo ya está en uso' }))

  await assert.rejects(register(account), (error) => {
    assert.ok(error instanceof DuplicateEmailError)
    assert.equal(error.message, 'Este correo ya está en uso')
    return true
  })
})

test('register keeps other conflicts as plain errors with the server detail', async (context) => {
  context.mock.method(globalThis, 'fetch', reply(409, { detail: 'El usuario ya existe bro' }))

  await assert.rejects(register(account), (error) => {
    assert.ok(!(error instanceof DuplicateEmailError))
    assert.equal(error.message, 'El usuario ya existe bro')
    return true
  })
})

test('register falls back to a generic message when the error has no string detail', async (context) => {
  context.mock.method(globalThis, 'fetch', reply(422, { detail: [{ msg: 'invalid' }] }))
  await assert.rejects(register(account), { message: 'Error al registrar usuario' })

  context.mock.method(globalThis, 'fetch', reply(500))
  await assert.rejects(register(account), { message: 'Error al registrar usuario' })
})

test('register propagates network failures', async (context) => {
  context.mock.method(globalThis, 'fetch', async () => { throw new TypeError('Failed to fetch') })

  await assert.rejects(register(account), { name: 'TypeError', message: 'Failed to fetch' })
})

test('login posts only email and password and returns the session payload', async (context) => {
  const session = { token: 'abc', user: { id: 1 } }
  const fetchMock = context.mock.method(globalThis, 'fetch', reply(200, session))

  assert.deepEqual(await login(account), session)

  const [url, request] = fetchMock.mock.calls[0].arguments
  assert.equal(url, '/api/v1/auth/login')
  assert.deepEqual(JSON.parse(request.body), { email: account.email, password: account.password })
})

test('login returns actionable guidance for a 401 without leaking server detail', async (context) => {
  const detail = 'No account exists for ana@example.test'
  context.mock.method(globalThis, 'fetch', reply(401, { detail }))

  await assert.rejects(login(account), (error) => {
    assert.equal(error.message, 'Email or password is incorrect. Check both and try again.')
    assert.ok(!error.message.includes(detail), 'Login error must not expose server detail')
    return true
  })
})

test('login returns a generic retry message for a non-401 HTTP failure without JSON', async (context) => {
  context.mock.method(globalThis, 'fetch', reply(502))
  await assert.rejects(login(account), { message: 'Could not sign in. Please try again.' })
})

test('login propagates network failures and the default export exposes both calls', async (context) => {
  context.mock.method(globalThis, 'fetch', async () => { throw new TypeError('Failed to fetch') })

  await assert.rejects(login(account), { message: 'Failed to fetch' })
  assert.equal(authService.login, login)
  assert.equal(authService.register, register)
})
