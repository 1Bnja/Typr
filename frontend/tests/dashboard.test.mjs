import assert from 'node:assert/strict'
import test from 'node:test'
import { getMyStats } from '../src/features/stats/utils/stats.js'

const entry = (gameId, ppm, extra = {}) => ({
    gameId, finishedAt: '2026-11-10T12:00:00Z', mode: 'singleplayer', language: 'eng',
    difficulty: 'medium', ppm, precisionPct: 98.44, score: 59, timeMs: 30000, progress: 1,
    position: null, ...extra,
})

const payload = {
    summary: {
        totalMatches: 12, practiceMatches: 9, multiplayerMatches: 3,
        averagePpm: 48.5, averagePrecisionPct: 96.2, bestPpm: 61,
    },
    trend: [],
    history: [entry(12, 61), entry(11, 57)],
    hasMore: true,
}

test('the profile fetches its five newest matches with the bearer token', async (context) => {
    const fetchMock = context.mock.method(globalThis, 'fetch', async () => ({ ok: true, json: async () => payload }))
    const controller = new AbortController()
    const data = await getMyStats('token', { offset: 0, limit: 5 }, controller.signal)
    const [url, request] = fetchMock.mock.calls[0].arguments
    assert.equal(url, '/api/v1/users/me/stats?offset=0&limit=5')
    assert.equal(request.headers.Authorization, 'Bearer token')
    assert.equal(request.signal, controller.signal)
    assert.deepEqual(data, payload)
})

test('the profile stats request rejects when stats cannot be loaded', async (context) => {
    context.mock.method(globalThis, 'fetch', async () => ({ ok: false }))
    await assert.rejects(
        getMyStats('token', { offset: 0, limit: 5 }),
        /Could not load your stats\. Please try again\./,
    )
})
