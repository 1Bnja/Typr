import assert from 'node:assert/strict'
import test from 'node:test'
import { CLOSE_REASONS, ROOM_ERRORS, roomErrorMessage } from '../src/features/rooms/constants.js'
import {
  RoomRequestError, closeRoom, createRoom, getMyRoom, joinRoom, kickMember, leaveRoom, roomSocketUrl, updateRoom,
} from '../src/features/rooms/services/rooms-service.js'
import { applyRaceInput, initialRaceInput, raceInputValue } from '../src/features/rooms/utils/race-input.js'
import { canStartRace, initialRoomState, roomReducer } from '../src/features/rooms/utils/room-state.js'

const CONTENT = 'hola mundo'

// --- bloqueo del cursor (HU-03) ---

test('correct characters advance one by one', () => {
  let state = initialRaceInput()
  state = applyRaceInput(state, 'h', CONTENT)
  state = applyRaceInput(state, 'ho', CONTENT)
  assert.deepEqual(state, { typed: 2, errors: 0, wrong: null })
  assert.equal(raceInputValue(state, CONTENT), 'ho')
})

test('a mistake blocks the cursor and freezes progress until it is deleted', () => {
  let state = applyRaceInput(initialRaceInput(2), 'hox', CONTENT)
  assert.deepEqual(state, { typed: 2, errors: 1, wrong: 'x' })
  assert.equal(raceInputValue(state, CONTENT), 'hox')

  // Seguir escribiendo sin borrar el error no avanza ni suma más errores.
  for (const attempt of ['hoxl', 'hoxla', 'hol', 'hola']) {
    assert.equal(applyRaceInput(state, attempt, CONTENT), state)
  }

  state = applyRaceInput(state, 'ho', CONTENT)
  assert.deepEqual(state, { typed: 2, errors: 1, wrong: null })
  state = applyRaceInput(state, 'hol', CONTENT)
  assert.deepEqual(state, { typed: 3, errors: 1, wrong: null })
})

test('what was typed correctly cannot be deleted or replaced', () => {
  const state = initialRaceInput(4)
  for (const attempt of ['hol', '', 'hxla', 'hola']) {
    assert.equal(applyRaceInput(state, attempt, CONTENT), state)
  }
})

test('several characters at once stop at the first mistake', () => {
  assert.deepEqual(applyRaceInput(initialRaceInput(), 'hola', CONTENT), { typed: 4, errors: 0, wrong: null })
  assert.deepEqual(applyRaceInput(initialRaceInput(), 'hoxa mundo', CONTENT), { typed: 2, errors: 1, wrong: 'x' })
})

test('the text ends exactly at its last character', () => {
  const state = applyRaceInput(initialRaceInput(9), `${CONTENT}!!`, CONTENT)
  assert.deepEqual(state, { typed: CONTENT.length, errors: 0, wrong: null })
  assert.equal(applyRaceInput(state, `${CONTENT}x`, CONTENT), state)
})

test('resuming keeps the progress and mistakes already counted', () => {
  const state = applyRaceInput(initialRaceInput(5, 3), 'hola m', CONTENT)
  assert.deepEqual(state, { typed: 6, errors: 3, wrong: null })
})

// --- estado de la sala ---

const room = (members, status = 'waiting') => ({ code: 'ABC234', status, members })
const member = (id, extra = {}) => ({ id, username: `user${id}`, isHost: false, isReady: false, connected: true, ...extra })
const players = [
  { userId: 1, username: 'ana', progress: 0, finished: false },
  { userId: 2, username: 'beto', progress: 0, finished: false },
]
const raceStart = {
  type: 'race_start', round: 1, rounds: 2, text: { id: 7, content: CONTENT }, timeLimitMs: 4000,
  elapsedMs: 0, players, receivedAt: 10_000,
}

test('the race needs two connected players with every guest ready', () => {
  const host = member(1, { isHost: true })
  assert.equal(canStartRace(room([host])), false)
  assert.equal(canStartRace(room([host, member(2)])), false)
  assert.equal(canStartRace(room([host, member(2, { isReady: true, connected: false })])), false)
  assert.equal(canStartRace(room([host, member(2, { isReady: true })])), true)
  assert.equal(canStartRace(room([host, member(2, { isReady: true })], 'in progress')), false)
})

test('a match flows from countdown to race to results and back to the lobby', () => {
  let state = roomReducer(initialRoomState, { type: 'room_state', room: room([member(1)]) })
  assert.equal(state.phase, 'lobby')

  state = roomReducer(state, { type: 'countdown', round: 1, rounds: 2, seconds: 3 })
  assert.equal(state.phase, 'countdown')
  assert.deepEqual(state.countdown, { round: 1, rounds: 2, seconds: 3 })

  state = roomReducer(state, raceStart)
  assert.equal(state.phase, 'racing')
  assert.equal(state.race.text.content, CONTENT)
  assert.equal(state.race.startedAt, 10_000)
  assert.deepEqual(state.race.you, { typed: 0, errors: 0 })

  state = roomReducer(state, { type: 'progress_update', userId: 2, progress: 0.5, finished: false })
  assert.deepEqual(state.race.players.map((player) => player.progress), [0, 0.5])

  // Un cambio de la sala durante la carrera no interrumpe la vista.
  state = roomReducer(state, { type: 'room_state', room: room([member(1)], 'in progress') })
  assert.equal(state.phase, 'racing')

  state = roomReducer(state, { type: 'race_end', round: 1, rounds: 2, results: [{ userId: 1 }], nextRoundInS: 8 })
  assert.equal(state.phase, 'results')
  assert.equal(state.race, null)
  assert.equal(state.results.nextRoundInS, 8)

  state = roomReducer(state, { type: 'room_state', room: room([member(1)]) })
  assert.equal(state.phase, 'results')
  state = roomReducer(state, { type: 'dismiss_results' })
  assert.equal(state.phase, 'lobby')
  assert.equal(state.results, null)
})

test('final match results retain average standings until the room return', () => {
  const standings = [{ userId: 2, position: 1, averageScore: 85 }, { userId: 1, position: 2, averageScore: 60 }]
  let state = roomReducer(initialRoomState, {
    type: 'race_end', round: 2, rounds: 2, results: [{ userId: 1 }],
    nextRoundInS: null, matchResults: standings, returnToRoomInS: 15, receivedAt: 10_000,
  })
  assert.deepEqual(state.results.matchResults, standings)
  assert.equal(state.results.returnToRoomInS, 15)
  assert.equal(state.results.receivedAt, 10_000)
  state = roomReducer(state, { type: 'room_state', room: room([member(1)], 'waiting') })
  assert.equal(state.phase, 'results')
  assert.deepEqual(state.results.matchResults, standings)
  state = roomReducer(state, { type: 'dismiss_results' })
  assert.equal(state.phase, 'lobby')
})

test('reconnecting mid-race resumes the clock and the own progress', () => {
  const state = roomReducer(initialRoomState, { ...raceStart, elapsedMs: 1500, you: { typed: 4, errors: 1 } })
  assert.equal(state.race.startedAt, 8500)
  assert.deepEqual(state.race.you, { typed: 4, errors: 1 })
})

test('a cancelled match returns to the lobby', () => {
  for (const message of [{ type: 'countdown', round: 1, rounds: 1, seconds: 3 }, raceStart]) {
    let state = roomReducer(initialRoomState, message)
    state = roomReducer(state, { type: 'room_state', room: room([member(1)]) })
    assert.equal(state.phase, 'lobby')
    assert.equal(state.race, null)
  }
})

test('errors are kept until cleared and unknown messages are ignored', () => {
  let state = roomReducer(initialRoomState, { type: 'error', code: 'players_not_ready', detail: 'x' })
  assert.equal(roomErrorMessage(state.error), ROOM_ERRORS.players_not_ready)
  assert.equal(roomReducer(state, { type: 'player_joined', userId: 2 }), state)
  assert.equal(roomReducer(state, { type: 'progress_update', userId: 2, progress: 1, finished: true }), state)
  state = roomReducer(state, { type: 'clear_error' })
  assert.equal(state.error, null)
  assert.match(roomErrorMessage({ code: 'nope' }), /Something went wrong/)
  assert.ok(CLOSE_REASONS[4404])
})

// --- servicio REST ---

const mockFetch = (context, response) => context.mock.method(globalThis, 'fetch', async () => response)

test('room requests use the right method, path, body and bearer token', async (context) => {
  const fetchMock = mockFetch(context, { ok: true, status: 200, json: async () => ({ code: 'ABC234' }) })
  await getMyRoom('token')
  await createRoom('token', { language: 'spa', difficulty: 'easy', rounds: 3, timeLimitS: null })
  await joinRoom('token', 'abc234')
  await updateRoom('token', 'ABC234', { rounds: 5 })
  await kickMember('token', 'ABC234', 9)

  const calls = fetchMock.mock.calls.map(({ arguments: [url, request] }) => [request.method, url, request.body])
  assert.deepEqual(calls, [
    ['GET', '/api/v1/rooms/me', undefined],
    ['POST', '/api/v1/rooms', '{"language":"spa","difficulty":"easy","rounds":3,"timeLimitS":null}'],
    ['POST', '/api/v1/rooms/abc234/join', undefined],
    ['PATCH', '/api/v1/rooms/ABC234', '{"rounds":5}'],
    ['DELETE', '/api/v1/rooms/ABC234/members/9', undefined],
  ])
  for (const { arguments: [, request] } of fetchMock.mock.calls) {
    assert.equal(request.headers.Authorization, 'Bearer token')
  }
})

test('leaving and closing resolve with no body', async (context) => {
  const fetchMock = mockFetch(context, { ok: true, status: 204, json: async () => { throw new Error('empty') } })
  assert.equal(await leaveRoom('token', 'ABC234'), null)
  assert.equal(await closeRoom('token', 'ABC234'), null)
  assert.deepEqual(
    fetchMock.mock.calls.map(({ arguments: [url, request] }) => [request.method, url]),
    [['POST', '/api/v1/rooms/ABC234/leave'], ['DELETE', '/api/v1/rooms/ABC234']],
  )
})

test('rejections carry the reason code from the API', async (context) => {
  mockFetch(context, {
    ok: false, status: 409, json: async () => ({ detail: { code: 'room_full', message: 'La sala está llena.' } }),
  })
  await assert.rejects(joinRoom('token', 'ABC234'), (error) => {
    assert.ok(error instanceof RoomRequestError)
    assert.equal(error.code, 'room_full')
    assert.equal(error.status, 409)
    assert.equal(roomErrorMessage(error), ROOM_ERRORS.room_full)
    return true
  })
})

test('unexpected failures fall back to an unknown code', async (context) => {
  mockFetch(context, { ok: false, status: 422, json: async () => ({ detail: [{ msg: 'invalid' }] }) })
  await assert.rejects(joinRoom('token', 'no'), (error) => error.code === 'unknown')
})

test('the socket URL follows the page protocol and host', () => {
  assert.equal(
    roomSocketUrl('ABC234', { protocol: 'https:', host: 'typr.example' }),
    'wss://typr.example/api/v1/ws/rooms/ABC234',
  )
  assert.equal(
    roomSocketUrl('ABC234', { protocol: 'http:', host: 'localhost:5173' }),
    'ws://localhost:5173/api/v1/ws/rooms/ABC234',
  )
})
