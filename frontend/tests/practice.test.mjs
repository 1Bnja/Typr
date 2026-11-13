import assert from 'node:assert/strict'
import test from 'node:test'
import { getRandomText, savePracticeMatch } from '../src/features/practice/services/practice-service.js'
import { calculatePpm, calculatePrecision, calculateScore } from '../src/features/practice/utils/metrics.js'

test('practice requests a saved phrase with filters, authentication and previous ID', async (context) => {
  const saved = { id: 12, content: 'A phrase already saved in the database.', language: 'eng', difficulty: 'medium' }
  const fetchMock = context.mock.method(globalThis, 'fetch', async () => ({ ok: true, json: async () => saved }))
  assert.deepEqual(await getRandomText('test-token', { language: 'eng', difficulty: 'medium', previousId: 7 }), saved)
  const [url, request] = fetchMock.mock.calls[0].arguments
  const parsed = new URL(url, 'http://localhost')
  assert.equal(parsed.pathname, '/api/v1/texts/random')
  assert.equal(parsed.searchParams.get('language'), 'eng')
  assert.equal(parsed.searchParams.get('difficulty'), 'medium')
  assert.equal(parsed.searchParams.get('excludeId'), '7')
  assert.equal(request.headers.Authorization, 'Bearer test-token')
})

test('practice reports missing saved phrases instead of generating local text', async (context) => {
  const fetchMock = context.mock.method(globalThis, 'fetch', async () => ({
    ok: false,
    json: async () => ({ detail: 'No hay frases guardadas para este idioma y dificultad.' }),
  }))
  await assert.rejects(
    getRandomText('token', { language: 'spa', difficulty: 'easy' }),
    /No hay frases guardadas/,
  )
  assert.equal(fetchMock.mock.callCount(), 1)
})

test('practice rejects an incomplete saved phrase response', async (context) => {
  context.mock.method(globalThis, 'fetch', async () => ({
    ok: true,
    json: async () => ({ content: 'Unsaved text', language: 'spa', difficulty: 'easy' }),
  }))
  await assert.rejects(getRandomText('token', { language: 'spa', difficulty: 'easy' }), /no es válida/)
})

test('metrics include corrected mistakes and handle an idle timer', () => {
  assert.equal(calculatePpm(250, 60000), 50)
  assert.equal(calculatePpm(1, 0), 0)
  assert.equal(calculatePrecision(0, 0), 100)
  assert.equal(calculatePrecision(11, 1), 90.9)
  assert.equal(calculateScore(50, 90), 45)
})

test('saving practice sends the existing text ID, metrics and bearer token', async (context) => {
  const saved = { id: 7, textId: 11, score: 38 }
  const fetchMock = context.mock.method(globalThis, 'fetch', async () => ({
    ok: true,
    json: async () => saved,
  }))
  const result = await savePracticeMatch('test-token', {
    textId: 11,
    timeMs: 30000, ppm: 40, precisionPct: 95, progress: 1, score: 999,
    speedHistory: [{ timeMs: 30000, ppm: 40, errors: 1 }],
  })
  const [url, request] = fetchMock.mock.calls[0].arguments
  assert.equal(url, '/api/v1/matches/practice')
  assert.equal(request.method, 'POST')
  assert.equal(request.headers.Authorization, 'Bearer test-token')
  assert.deepEqual(JSON.parse(request.body), {
    textId: 11,
    timeMs: 30000, ppm: 40, precisionPct: 95, progress: 1,
  })
  assert.deepEqual(result, saved)
})

test('saving with an existing text sends its ID and propagates API errors', async (context) => {
  const fetchMock = context.mock.method(globalThis, 'fetch', async () => ({
    ok: false,
    json: async () => ({ detail: 'El texto no existe.' }),
  }))
  await assert.rejects(
    savePracticeMatch('test-token', { textId: 9, timeMs: 1000, ppm: 40, precisionPct: 95, progress: 1 }),
    /El texto no existe\./,
  )
  const payload = JSON.parse(fetchMock.mock.calls[0].arguments[1].body)
  assert.equal(payload.textId, 9)
  assert.equal('text' in payload, false)
})

test('an invalid success response is reported as a save error', async (context) => {
  context.mock.method(globalThis, 'fetch', async () => ({
    ok: true,
    json: async () => null,
  }))
  await assert.rejects(
    savePracticeMatch('test-token', { textId: 9, timeMs: 1000, ppm: 40, precisionPct: 95, progress: 1 }),
    /Could not read the saved match/,
  )
})

test('saving keeps the chosen practice difficulty', async (context) => {
  const fetchMock = context.mock.method(globalThis, 'fetch', async () => ({
    ok: true, json: async () => ({ id: 5, textId: 7, difficulty: 'easy' }),
  }))
  await savePracticeMatch('token', {
    textId: 7, difficulty: 'easy',
    timeMs: 30000, ppm: 30, precisionPct: 95, progress: 1,
  })
  assert.equal(JSON.parse(fetchMock.mock.calls[0].arguments[1].body).difficulty, 'easy')
})

test('history and ranking requests carry filters, authentication and cancellation', async (context) => {
  const { getPracticeHistory, getMonthlyLeaderboard } = await import('../src/features/practice/services/practice-service.js')
  const fetchMock = context.mock.method(globalThis, 'fetch', async () => ({ ok: true, json: async () => [] }))
  const controller = new AbortController()
  await getPracticeHistory('token', { difficulty: 'advanced', language: 'eng', offset: 10, limit: 11 }, controller.signal)
  await getMonthlyLeaderboard('token', { difficulty: 'easy', month: '2026-11', language: 'spa' }, controller.signal)
  const [historyUrl, request] = fetchMock.mock.calls[0].arguments
  const historyParams = new URL(historyUrl, 'http://localhost').searchParams
  assert.equal(historyParams.get('difficulty'), 'advanced')
  assert.equal(historyParams.get('offset'), '10')
  assert.equal(historyParams.get('limit'), '11')
  assert.equal(request.headers.Authorization, 'Bearer token')
  assert.equal(request.signal, controller.signal)
  const rankingUrl = new URL(fetchMock.mock.calls[1].arguments[0], 'http://localhost')
  assert.equal(rankingUrl.pathname, '/api/v1/matches/leaderboard')
  assert.equal(rankingUrl.searchParams.get('month'), '2026-11')
  assert.equal(rankingUrl.searchParams.get('language'), 'spa')
})

test('record requests propagate failures for the retry state', async (context) => {
  const { getPracticeHistory } = await import('../src/features/practice/services/practice-service.js')
  context.mock.method(globalThis, 'fetch', async () => ({ ok: false }))
  await assert.rejects(getPracticeHistory('token', {}), /Could not load/)
})
