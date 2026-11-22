import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { randomBytes } from 'node:crypto'
import { Given, Then, When } from '@cucumber/cucumber'
import { expect } from '@playwright/test'
import { httpError, origin } from './browser.mjs'

const rooms = `${origin}/api/v1/rooms`
const creationRules = [
  ['Room type', 'Quick match', 'type', 'quick'],
  ['Language', 'English', 'language', 'eng'],
  ['Difficulty', 'Medium', 'difficulty', 'medium'],
  ['Rounds', '3 rounds', 'rounds', 3],
  ['Time limit', '1 min 30 s', 'timeLimitS', 90],
]

const auth = world => ({ headers: { Authorization: `Bearer ${world.credentials[0]}` } })
const trigger = (page, label) => page.getByRole('button', { name: new RegExp(`^${label} `) })
const rules = fields => Object.fromEntries(fields.map(([, , key, value]) => [key, value]))
const actualRules = (room, expected) => Object.fromEntries(Object.keys(expected).map(key => [key, room[key]]))

async function choose(page, label, option) {
  await trigger(page, label).click()
  await page.getByRole('listbox', { name: label, exact: true })
    .getByRole('option', { name: option, exact: true }).click()
}

async function assertWaitingHost(world, room) {
  const { id } = JSON.parse(world.credentials[1])
  assert.equal(room.status, 'waiting')
  assert.equal(room.hostId, id)
  assert.deepEqual(room.members.map(({ id, username, isHost }) => ({ id, username, isHost })), [
    { id, username: world.account.username, isHost: true },
  ])
  await expect(world.page.getByRole('button', { name: 'Start race', exact: true })).toBeVisible()
  const roster = world.page.getByRole('listitem').filter({ hasText: world.account.username })
  await expect(roster.getByText('Host', { exact: true })).toBeVisible()
  await expect(roster.getByText('You', { exact: true })).toBeVisible()
}

Given('I do not belong to a room', async function () {
  const response = await this.request.get(`${rooms}/me`, auth(this))
  assert.equal(response.status(), 200)
  assert.equal(await response.json(), null)
})

When('I select the room type, language, difficulty, rounds, and time limit and create the room', async function () {
  await this.page.goto(`${origin}/rooms`)
  for (const [label, option] of creationRules) await choose(this.page, label, option)
  const [response] = await Promise.all([
    this.page.waitForResponse(res => res.url() === rooms && res.request().method() === 'POST'),
    this.page.getByRole('button', { name: 'Create room', exact: true }).click(),
  ])
  assert.equal(response.status(), 201)
  const expected = rules(creationRules)
  assert.deepEqual(response.request().postDataJSON(), expected)
  this.room = await response.json()
  assert.deepEqual(actualRules(this.room, expected), expected)
})

Then('the new room is waiting and lists me as its host and member', async function () {
  await assertWaitingHost(this, this.room)
})

Then('its unique access code opens that room', async function () {
  const { code } = this.room
  assert.match(code, /^[A-Z0-9]{6}$/)
  await expect(this.page).toHaveURL(`${origin}/rooms/${code}`)
  await expect(this.page.getByLabel(`Room code ${code.split('').join(' ')}`)).toHaveText(code)
  const response = await this.request.get(`${rooms}/${code}`, auth(this))
  assert.equal(response.status(), 200)
  assert.deepEqual(await response.json(), this.room)

  const database = process.env.TYPR_BROWSER_FIXTURE_DB
  assert.match(database ?? '', /^typr-registration-[\da-f-]{36}-db$/)
  const unique = execFileSync('docker', [
    'exec', database, 'psql', '-XAt', '-U', 'typr_test', '-d', 'typr_registration_test',
    '-v', 'ON_ERROR_STOP=1', '-c', `
      SELECT EXISTS (
        SELECT 1 FROM pg_index i JOIN pg_attribute a
          ON a.attrelid = i.indrelid AND a.attnum = i.indkey[0]
        WHERE i.indrelid = 'rooms'::regclass AND a.attname = 'code'
          AND i.indisunique AND i.indisvalid AND i.indpred IS NULL AND i.indnkeyatts = 1
      );
    `,
  ], { encoding: 'utf8', timeout: 5_000 }).trim()
  assert.equal(unique, 't')
  this.log(`Room creation: ${JSON.stringify({
    post: 201, lookup: response.status(), code, status: this.room.status, hostId: this.room.hostId,
    members: this.room.members.length, uniqueCodeIndex: true, rules: rules(creationRules),
  })}`)
})

Given('I host a waiting room', async function () {
  const response = await this.request.post(rooms, {
    ...auth(this), data: { language: 'spa', difficulty: 'easy' },
  })
  assert.equal(response.status(), 201)
  this.room = await response.json()
  await this.page.goto(`${origin}/rooms/${this.room.code}`)
  await assertWaitingHost(this, this.room)
})

When('I change the language, difficulty, rounds, and time limit through the lobby', async function () {
  this.patchStatuses = []
  for (const [label, option, key, value] of creationRules.slice(1)) {
    const [response] = await Promise.all([
      this.page.waitForResponse(res => res.url() === `${rooms}/${this.room.code}` && res.request().method() === 'PATCH'),
      choose(this.page, label, option),
    ])
    this.patchStatuses.push(response.status())
    assert.equal(response.status(), 200)
    assert.deepEqual(response.request().postDataJSON(), { [key]: value })
    assert.equal((await response.json())[key], value)
    await expect(trigger(this.page, label)).toHaveAccessibleName(`${label} ${option}`)
  }
})

Then('the updated rules persist and are visible after reloading the waiting lobby', async function () {
  // The reloaded lobby receives its state over WebSocket, not via a room GET.
  await this.page.reload()
  const response = await this.request.get(`${rooms}/${this.room.code}`, auth(this))
  assert.equal(response.status(), 200)
  const updated = await response.json()
  const expected = rules(creationRules.slice(1))
  assert.equal(updated.id, this.room.id)
  assert.equal(updated.type, this.room.type)
  assert.deepEqual(actualRules(updated, expected), expected)
  await assertWaitingHost(this, updated)
  for (const [label, option] of creationRules.slice(1)) {
    await expect(trigger(this.page, label)).toHaveAccessibleName(`${label} ${option}`)
  }
  this.log(`Room configuration: ${JSON.stringify({
    code: updated.code, status: updated.status, hostId: updated.hostId, patch: this.patchStatuses,
    lookup: response.status(), before: actualRules(this.room, expected), after: actualRules(updated, expected),
  })}`)
})

const memberRow = (page, username) =>
  page.getByRole('listitem').filter({ has: page.getByText(username, { exact: true }) })

async function registerPeer(world) {
  const username = `peer_${randomBytes(6).toString('hex')}`
  const data = { username, email: `${username}@example.com`, password: 'LocalTest123!' }
  assert.equal((await world.request.post(`${origin}/api/v1/auth/register`, { data })).status(), 201)
  const login = await world.request.post(`${origin}/api/v1/auth/login`, { data })
  assert.equal(login.status(), 200)
  const { token, user } = await login.json()
  return { token, user, headers: { Authorization: `Bearer ${token}` } }
}

async function peerPage(world, { token, user }) {
  const { context } = await world.newContext({
    storageState: {
      cookies: [],
      origins: [{
        origin,
        localStorage: [
          { name: 'token', value: token },
          { name: 'user', value: JSON.stringify(user) },
        ],
      }],
    },
  })
  return context.newPage()
}

Given('another player belongs to the room in a separate browser context', async function () {
  const peer = await registerPeer(this)
  const { user, headers } = peer
  const joined = await this.request.post(`${rooms}/${this.room.code}/join`, { headers })
  assert.equal(joined.status(), 200)
  assert.equal((await joined.json()).status, 'waiting')

  const page = await peerPage(this, peer)
  const roomUrl = `${origin}/rooms/${this.room.code}`
  const socketClosed = page.waitForEvent('websocket', {
    predicate: socket => new URL(socket.url()).pathname.endsWith(`/${this.room.code}`),
  }).then(socket => {
    socket.once('close', () => { this.removedMember.socketClosed = true })
  })
  this.removedMember = { user, page, headers, socketClosed: false }
  await Promise.all([page.goto(roomUrl), socketClosed])
  await expect(memberRow(page, user.username).getByText('You', { exact: true })).toBeVisible()
  await expect(memberRow(this.page, user.username)).toBeVisible()
})

Given('another player belongs to no room and the waiting room has fewer than 10 players', async function () {
  this.joiningPeer = await registerPeer(this)
  const before = await this.request.get(`${rooms}/me`, { headers: this.joiningPeer.headers })
  assert.equal(before.status(), 200)
  assert.equal(await before.json(), null)
  assert.equal(this.room.status, 'waiting')
  assert.ok(this.room.members.length < 10)
  this.joiningPeer.page = await peerPage(this, this.joiningPeer)
})

When('that player enters the valid room code and submits the join form', async function () {
  const { page } = this.joiningPeer
  const code = await this.page.getByLabel(`Room code ${this.room.code.split('').join(' ')}`).innerText()
  await page.goto(`${origin}/rooms`)
  await page.getByRole('textbox', { name: 'Room code', exact: true }).fill(code)
  const [response] = await Promise.all([
    page.waitForResponse(res => res.url() === `${rooms}/${code}/join` && res.request().method() === 'POST'),
    page.getByRole('button', { name: 'Join room', exact: true }).click(),
  ])
  assert.equal(response.status(), 200)
  this.joinedRoom = await response.json()
})

When('I submit a code that does not match any available room', async function () {
  // The disposable fixture starts without rooms, and this scenario creates none.
  const code = 'ZZZZZZ'
  const path = `/api/v1/rooms/${code}/join`
  await this.page.goto(`${origin}/rooms`)
  await this.page.getByRole('textbox', { name: 'Room code', exact: true }).fill(code)
  this.expectResourceError(path, httpError(404))
  const [response] = await Promise.all([
    this.page.waitForResponse(res => res.url() === `${origin}${path}` && res.request().method() === 'POST'),
    this.page.getByRole('button', { name: 'Join room', exact: true }).click(),
  ])
  this.invalidJoin = response
})

Then('the join is rejected without navigation or a membership change', async function () {
  assert.equal(this.invalidJoin.status(), 404)
  assert.equal((await this.invalidJoin.json()).detail.code, 'room_not_found')
  const membership = await this.request.get(`${rooms}/me`, auth(this))
  assert.equal(membership.status(), 200)
  assert.equal(await membership.json(), null)
  await expect(this.page).toHaveURL(`${origin}/rooms`)
  this.log(`Rejected join: ${JSON.stringify({
    url: this.invalidJoin.url(), status: this.invalidJoin.status(), error: 'room_not_found',
    membershipStatus: membership.status(), membership: null, page: this.page.url(),
  })}`)
})

Then('the join form displays {string}', async function (message) {
  const form = this.page.locator('form').filter({
    has: this.page.getByRole('button', { name: 'Join room', exact: true }),
  })
  const alert = form.getByRole('alert')
  await expect(alert).toHaveText(message)
  await expect(alert).toBeVisible()
  this.log(`Visible join alert: ${await alert.textContent()}`)
})

Then('that player joins the waiting room as a member without host permissions', async function () {
  const { page, user } = this.joiningPeer
  const { id, code, hostId, status, members } = this.joinedRoom
  assert.equal(id, this.room.id)
  assert.equal(code, this.room.code)
  assert.equal(hostId, this.room.hostId)
  assert.equal(status, 'waiting')
  assert.equal(members.find(member => member.id === user.id)?.isHost, false)
  await expect(page).toHaveURL(`${origin}/rooms/${code}`)
  const row = memberRow(page, user.username)
  await expect(row.getByText('You', { exact: true })).toBeVisible()
  await expect(row.getByText('Host', { exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: /^(Start race|Close room|Remove .* from the room)$/ })).toHaveCount(0)
})

Then('the joining player sees the other members and the room settings', async function () {
  const { page, user } = this.joiningPeer
  await expect(memberRow(page, this.account.username).getByText('Host', { exact: true })).toBeVisible()
  const settings = page.getByRole('region', { name: 'Rules', exact: true })
  const displayedRules = {
    'Room type': 'Private', Language: 'Español', Difficulty: 'Easy', Rounds: '1 round', 'Time limit': 'Automatic',
  }
  for (const [label, value] of Object.entries(displayedRules)) {
    const rule = settings.locator('dl > div').filter({ has: page.getByText(label, { exact: true }) })
    await expect(rule.getByText(value, { exact: true })).toBeVisible()
    await expect(trigger(settings, label)).toHaveCount(0)
  }
  this.log(`Room join: ${JSON.stringify({
    code: this.room.code, membershipBefore: null, playersBefore: this.room.members.length,
    joinStatus: 200, roomStatus: this.joinedRoom.status, hostId: this.room.hostId,
    memberId: user.id, memberIsHost: false, hostControls: 0, displayedRules,
  })}`)
})

When('I remove that player through the lobby', async function () {
  const { id, username } = this.removedMember.user
  const [response] = await Promise.all([
    this.page.waitForResponse(res =>
      res.url() === `${rooms}/${this.room.code}/members/${id}` && res.request().method() === 'DELETE'),
    this.page.getByRole('button', { name: `Remove ${username} from the room`, exact: true }).click(),
  ])
  assert.equal(response.status(), 200)
  this.roomAfterRemoval = await response.json()
  this.removalStatus = response.status()
})

Then("the player is removed from the host's roster", async function () {
  await expect(memberRow(this.page, this.removedMember.user.username)).toHaveCount(0)
  await assertWaitingHost(this, this.roomAfterRemoval)
})

Then('the removed player is disconnected and no longer belongs to the room', async function () {
  const { page, headers, user } = this.removedMember
  const alert = page.getByRole('alert').getByRole('heading', { name: 'You are no longer in this room.' })
  await expect(alert).toBeVisible()
  await expect.poll(() => this.removedMember.socketClosed).toBe(true)
  const membership = await page.request.get(`${rooms}/me`, { headers })
  assert.equal(membership.status(), 200)
  assert.equal(await membership.json(), null)
  this.log(`Member removal: ${JSON.stringify({
    code: this.room.code, hostId: this.room.hostId, removedId: user.id,
    deleteStatus: this.removalStatus, roomStatus: this.roomAfterRemoval.status,
    remainingMembers: this.roomAfterRemoval.members.map(member => member.id),
    socketClosed: this.removedMember.socketClosed, memberAlert: await alert.textContent(),
    membershipStatus: membership.status(), membership: null,
  })}`)
})

Given('a not-ready member is viewing my waiting room in a separate browser context', async function () {
  const peer = await registerPeer(this)
  const joined = await this.request.post(`${rooms}/${this.room.code}/join`, { headers: peer.headers })
  assert.equal(joined.status(), 200)
  const room = await joined.json()
  assert.equal(room.status, 'waiting')
  assert.equal(room.members.find(member => member.id === peer.user.id)?.isReady, false)

  const page = await peerPage(this, peer)
  this.readyPeer = { ...peer, page }
  await page.goto(`${origin}/rooms/${this.room.code}`)
  const readyButton = page.getByRole('button', { name: 'I am ready', exact: true })
  await expect(readyButton).toHaveAttribute('aria-pressed', 'false')
  await expect(memberRow(this.page, peer.user.username).getByText('Not ready', { exact: true })).toBeVisible()
})

When('the member presses the ready button', async function () {
  await this.readyPeer.page.getByRole('button', { name: 'I am ready', exact: true }).click()
})

Then('the member is registered as ready', async function () {
  const { page, user } = this.readyPeer
  await expect(page.getByRole('button', { name: 'Ready — tap to undo', exact: true, pressed: true })).toBeVisible()
  const response = await this.request.get(`${rooms}/${this.room.code}`, auth(this))
  assert.equal(response.status(), 200)
  const room = await response.json()
  const member = room.members.find(member => member.id === user.id)
  assert.equal(member?.isReady, true)
  this.log(`Member readiness: GET ${response.status()}, isReady=${member.isReady}, member control pressed=true`)
})

Then("the host sees that member's updated ready status", async function () {
  const status = memberRow(this.page, this.readyPeer.user.username).getByText('Ready', { exact: true })
  await expect(status).toBeVisible()
  this.log(`Host roster: Not ready → ${await status.innerText()} without reload`)
})
