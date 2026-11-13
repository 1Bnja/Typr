import assert from 'node:assert/strict'
import test from 'node:test'
import { DIFFICULTIES, LANGUAGES } from '../src/features/practice/constants.js'
import { WORD_LISTS } from '../src/features/practice/data/word-lists.js'
import { generatePracticeText } from '../src/features/practice/utils/generate-text.js'
import { getRandomText } from '../src/features/practice/services/practice-service.js'
import { calculatePpm, calculatePrecision, calculateScore } from '../src/features/practice/utils/metrics.js'

for (const { value: language } of LANGUAGES) {
  for (const { value: difficulty, wordCount } of DIFFICULTIES) {
    test(`${language}/${difficulty}: generates the requested words without changing the list`, () => {
      const original = [...WORD_LISTS[language][difficulty]]
      for (let attempt = 0; attempt < 20; attempt++) {
        const text = generatePracticeText(language, difficulty)
        const words = text.content.split(' ')
        const plainWords = words.map((word) => word.replace(/[,.]/g, '').toLowerCase())
        assert.equal(words.length, wordCount)
        assert.equal(new Set(plainWords).size, wordCount)
        assert.ok(plainWords.every((word) => original.map((item) => item.toLowerCase()).includes(word)))
        assert.equal(text.id, null)
        assert.equal(text.language, language)
        assert.equal(text.difficulty, difficulty)
        if (difficulty === 'advanced') {
          assert.equal(words.filter((word) => word.endsWith(',')).length, 4)
          assert.equal(words.filter((word) => word.endsWith('.')).length, 4)
          assert.equal(words.filter((word) => /^[A-ZÁÉÍÓÚÑ]/.test(word)).length, 4)
        } else {
          assert.equal(text.content, text.content.toLowerCase())
          assert.doesNotMatch(text.content, /[,.]/)
        }
      }
      assert.deepEqual(WORD_LISTS[language][difficulty], original)
    })
  }
}

test('invalid settings fall back to Spanish and easy', () => {
  const text = generatePracticeText('unknown', 'unknown')
  assert.equal(text.language, 'spa')
  assert.equal(text.difficulty, 'easy')
  assert.equal(text.content.split(' ').length, 20)
})

test('consecutive tests generate different word orders', () => {
  const texts = new Set(Array.from({ length: 10 }, () => generatePracticeText('spa', 'easy').content))
  assert.ok(texts.size > 1)
})

test('a repeated random order is replaced without losing the difficulty format', async (context) => {
  context.mock.method(Math, 'random', () => 0.5)
  for (const { value: language } of LANGUAGES) {
    for (const { value: difficulty, wordCount } of DIFFICULTIES) {
      const previous = await getRandomText({ language, difficulty })
      const next = await getRandomText({ language, difficulty, previousContent: previous.content })
      assert.notEqual(next.content, previous.content)
      assert.equal(next.content.split(' ').length, wordCount)
      assert.equal(next.language, language)
      assert.equal(next.difficulty, difficulty)
      if (difficulty === 'advanced') {
        const words = next.content.split(' ')
        assert.equal(words.filter((word) => /^[A-ZÁÉÍÓÚÑ]/.test(word)).length, 4)
        assert.equal(words.filter((word) => word.endsWith(',')).length, 4)
        assert.equal(words.filter((word) => word.endsWith('.')).length, 4)
      }
    }
  }
})

test('local mode works without requesting the API', async (context) => {
  const fetchMock = context.mock.method(globalThis, 'fetch', () => {
    throw new Error('The local mode must not request the API')
  })
  const text = await getRandomText({ language: 'eng', difficulty: 'advanced' })
  assert.equal(fetchMock.mock.callCount(), 0)
  assert.equal(text.content.split(' ').length, 40)
})

test('metrics include corrected mistakes and handle an idle timer', () => {
  assert.equal(calculatePpm(250, 60000), 50)
  assert.equal(calculatePpm(1, 0), 0)
  assert.equal(calculatePrecision(0, 0), 100)
  assert.equal(calculatePrecision(11, 1), 90.9)
  assert.equal(calculateScore(50, 90), 45)
})

test('saving a local result sends the text, metrics and bearer token', async (context) => {
  const { savePracticeMatch } = await import('../src/features/practice/services/practice-service.js')
  const saved = { id: 7, textId: 11, score: 38 }
  const fetchMock = context.mock.method(globalThis, 'fetch', async () => ({
    ok: true,
    json: async () => saved,
  }))
  const result = await savePracticeMatch('test-token', {
    text: { content: 'casa mesa gato', language: 'spa' },
    timeMs: 30000, typed: 'casa mesa gato', keystrokes: 16, errors: 1,
    ppm: 40, precisionPct: 95, progress: 1, score: 999,
    speedHistory: [{ timeMs: 30000, ppm: 40, errors: 1 }],
  })
  const [url, request] = fetchMock.mock.calls[0].arguments
  assert.equal(url, '/api/v1/matches/practice')
  assert.equal(request.method, 'POST')
  assert.equal(request.headers.Authorization, 'Bearer test-token')
  // Solo señales crudas: PPM/precisión/score/progress no se envían.
  assert.deepEqual(JSON.parse(request.body), {
    text: { content: 'casa mesa gato', language: 'spa' },
    timeMs: 30000, typed: 'casa mesa gato', keystrokes: 16, errors: 1,
  })
  assert.deepEqual(result, saved)
})

test('saving with an existing text sends its ID and propagates API errors', async (context) => {
  const { savePracticeMatch } = await import('../src/features/practice/services/practice-service.js')
  const fetchMock = context.mock.method(globalThis, 'fetch', async () => ({
    ok: false,
    json: async () => ({ detail: 'El texto no existe.' }),
  }))
  await assert.rejects(
    savePracticeMatch('test-token', { textId: 9, timeMs: 1000, typed: 'hola', keystrokes: 4, errors: 0 }),
    /El texto no existe\./,
  )
  const payload = JSON.parse(fetchMock.mock.calls[0].arguments[1].body)
  assert.equal(payload.textId, 9)
  assert.equal('text' in payload, false)
})

test('an invalid success response is reported as a save error', async (context) => {
  const { savePracticeMatch } = await import('../src/features/practice/services/practice-service.js')
  context.mock.method(globalThis, 'fetch', async () => ({
    ok: true,
    json: async () => null,
  }))
  await assert.rejects(
    savePracticeMatch('test-token', { textId: 9, timeMs: 1000, typed: 'hola', keystrokes: 4, errors: 0 }),
    /Could not read the saved match/,
  )
})

test('saving keeps the chosen practice difficulty', async (context) => {
  const { savePracticeMatch } = await import('../src/features/practice/services/practice-service.js')
  const fetchMock = context.mock.method(globalThis, 'fetch', async () => ({
    ok: true, json: async () => ({ id: 5, textId: 7, difficulty: 'easy' }),
  }))
  await savePracticeMatch('token', {
    text: { content: 'casa mesa gato', language: 'spa' }, difficulty: 'easy',
    timeMs: 30000, typed: 'casa mesa gato', keystrokes: 14, errors: 0,
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
