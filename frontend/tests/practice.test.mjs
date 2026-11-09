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
