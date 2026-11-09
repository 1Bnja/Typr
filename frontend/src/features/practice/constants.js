export const USE_LOCAL_TEXTS = true

export const LANGUAGES = [
  { value: 'spa', label: 'Español' },
  { value: 'eng', label: 'English' },
]

export const DIFFICULTIES = [
  {
    value: 'easy',
    label: 'Easy',
    wordCount: 20,
    description: 'Short, everyday words. Lowercase, no punctuation.',
  },
  {
    value: 'medium',
    label: 'Medium',
    wordCount: 30,
    description: 'Longer words, including Spanish accents and ñ.',
  },
  {
    value: 'advanced',
    label: 'Hard',
    wordCount: 40,
    description: 'Technical words with capitals, commas and periods.',
  },
]
