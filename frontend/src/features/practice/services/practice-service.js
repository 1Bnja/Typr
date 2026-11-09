import { USE_LOCAL_TEXTS } from '../constants.js'
import { generatePracticeText } from '../utils/generate-text.js'

export async function getRandomText({ language, difficulty }) {
  if (USE_LOCAL_TEXTS) return generatePracticeText(language, difficulty)

  const params = new URLSearchParams({ language, difficulty })
  try {
    const response = await fetch(`/api/v1/texts/random?${params}`)
    if (!response.ok) throw new Error('Text not available')
    const text = await response.json()
    if (!text?.content?.trim()) throw new Error('Text is empty')
    return text
  } catch {
    return generatePracticeText(language, difficulty)
  }
}

export async function savePracticeMatch(token, { textId, timeMs, ppm, precisionPct, progress }) {
  const response = await fetch('/api/v1/matches/practice', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ textId, timeMs, ppm, precisionPct, progress }),
  })

  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = data?.detail
    throw new Error(typeof detail === 'string' ? detail : 'Could not save the match')
  }
  return data
}
