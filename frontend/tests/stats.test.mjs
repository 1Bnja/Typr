import assert from 'node:assert/strict'
import test from 'node:test'
import { describeTrend, getMyStats, ordinal, toTrendData } from '../src/features/stats/utils/stats.js'

const point = (ppm, extra = {}) => ({
  gameId: ppm, finishedAt: '2026-11-10T12:00:00Z', mode: 'singleplayer', ppm, precisionPct: 95.04, ...extra,
})

test('trend points are numbered by match and keep one decimal of accuracy', () => {
  const data = toTrendData([point(40), point(45, { mode: 'multiplayer' })], 12)
  assert.deepEqual(data.map(({ match, ppm, precision, mode }) => [match, ppm, precision, mode]), [
    [11, 40, 95, 'singleplayer'],
    [12, 45, 95, 'multiplayer'],
  ])
})

test('the trend summary describes the change in speed', () => {
  assert.equal(describeTrend([]), '')
  assert.equal(describeTrend([point(40)]), 'Your first match: 40 words per minute.')
  assert.match(describeTrend([point(40), point(30), point(52)]), /went up 12 words per minute, from 40 to 52/)
  assert.match(describeTrend([point(52), point(40)]), /went down 12 words per minute, from 52 to 40/)
  assert.match(describeTrend([point(40), point(40)]), /held steady at 40/)
})

test('positions read as ordinals', () => {
  assert.deepEqual([1, 2, 3, 4, 11, 22].map(ordinal), ['1st', '2nd', '3rd', '4th', '11th', '22nd'])
})

test('stats requests carry the page and the bearer token', async (context) => {
  const fetchMock = context.mock.method(globalThis, 'fetch', async () => ({ ok: true, json: async () => ({ trend: [] }) }))
  const controller = new AbortController()
  await getMyStats('token', { offset: 20, limit: 10 }, controller.signal)
  const [url, request] = fetchMock.mock.calls[0].arguments
  assert.equal(url, '/api/v1/users/me/stats?offset=20&limit=10')
  assert.equal(request.headers.Authorization, 'Bearer token')
  assert.equal(request.signal, controller.signal)
})

test('a failed stats request is reported for the retry state', async (context) => {
  context.mock.method(globalThis, 'fetch', async () => ({ ok: false }))
  await assert.rejects(getMyStats('token'), /Could not load your stats/)
})
