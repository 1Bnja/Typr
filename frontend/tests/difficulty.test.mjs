import assert from 'node:assert/strict'
import test from 'node:test'
import { WORD_LISTS } from '../src/features/practice/data/word-lists.js'
import { generatePracticeText } from '../src/features/practice/utils/generate-text.js'

test('hard uses familiar words while keeping its longer, punctuated test', () => {
  for (const language of ['spa', 'eng']) {
    const words = WORD_LISTS[language].advanced
    assert.ok(words.length >= 40)
    assert.ok(words.every((word) => word.length <= 13))
    const text = generatePracticeText(language, 'advanced').content
    assert.equal(text.split(' ').length, 40)
    assert.match(text, /,/)
    assert.match(text, /\./)
    assert.match(text, /^[A-ZÁÉÍÓÚÑ]/)
  }
})
