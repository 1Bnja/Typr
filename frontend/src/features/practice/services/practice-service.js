import { USE_LOCAL_TEXTS } from '../constants.js'
import { generatePracticeText } from '../utils/generate-text.js'

export async function getRandomText({ language, difficulty, previousContent }) {
  if (USE_LOCAL_TEXTS) return generatePracticeText(language, difficulty, previousContent)

  const params = new URLSearchParams({ language, difficulty })
  try {
    const response = await fetch(`/api/v1/texts/random?${params}`)
    if (!response.ok) throw new Error('Text not available')
    const text = await response.json()
    if (!text?.content?.trim()) throw new Error('Text is empty')
    if (text.content.trim() === previousContent?.trim()) throw new Error('Text was already used')
    return text
  } catch {
    return generatePracticeText(language, difficulty, previousContent)
  }
}

export async function savePracticeMatch(token, { textId, text, difficulty, timeMs, typed, keystrokes, errors }) {
  const response = await fetch('/api/v1/matches/practice', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    // Solo señales crudas: el servidor calcula PPM, precisión y puntaje.
    body: JSON.stringify({ textId, text, difficulty, timeMs, typed, keystrokes, errors }),
  })

  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = data?.detail
    throw new Error(typeof detail === 'string' ? detail : 'Could not save the match')
  }
  if (data?.id == null || data?.textId == null) {
    throw new Error('Could not read the saved match')
  }
  return data
}

async function getPracticeData(path, token, params, signal) {
  const response = await fetch(`/api/v1/matches/${path}?${params}`, {
    headers: { Authorization: `Bearer ${token}` },
    signal,
  })
  if (!response.ok) throw new Error('Could not load your practice data. Please try again.')
  return response.json()
}

export function getPracticeHistory(token, { difficulty, language, offset = 0, limit = 11 }, signal) {
  const params = new URLSearchParams({ offset, limit })
  if (difficulty) params.set('difficulty', difficulty)
  if (language) params.set('language', language)
  return getPracticeData('practice', token, params, signal)
}

export function getMonthlyLeaderboard(token, { difficulty, language, month }, signal) {
  const params = new URLSearchParams({ difficulty, month })
  if (language) params.set('language', language)
  return getPracticeData('leaderboard', token, params, signal)
}
