import { DIFFICULTIES } from '../constants.js'
import { WORD_LISTS } from '../data/word-lists.js'

export function generatePracticeText(language, difficulty, previousContent = '') {
  const selectedLanguage = WORD_LISTS[language] ? language : 'spa'
  const level = DIFFICULTIES.find((option) => option.value === difficulty) ?? DIFFICULTIES[0]
  const words = [...WORD_LISTS[selectedLanguage][level.value]]

  for (let i = words.length - 1; i > 0; i--) {
    const randomIndex = Math.floor(Math.random() * (i + 1))
    const current = words[i]
    words[i] = words[randomIndex]
    words[randomIndex] = current
  }

  const selectedWords = words.slice(0, level.wordCount).map((word) => word.toLowerCase())

  if (selectedWords.join(' ') === previousContent.toLowerCase().replace(/[,.]/g, '')) {
    const firstWord = selectedWords[0]
    selectedWords[0] = selectedWords[1]
    selectedWords[1] = firstWord
  }

  if (level.value === 'advanced') {
    for (let i = 0; i < selectedWords.length; i++) {
      if (i % 10 === 0) {
        const word = selectedWords[i]
        selectedWords[i] = word[0].toUpperCase() + word.slice(1)
      }
      if ((i + 1) % 10 === 0) selectedWords[i] += '.'
      else if ((i + 1) % 5 === 0) selectedWords[i] += ','
    }
  }

  return {
    id: null,
    content: selectedWords.join(' '),
    language: selectedLanguage,
    difficulty: level.value,
    idealTimeMs: null,
  }
}
