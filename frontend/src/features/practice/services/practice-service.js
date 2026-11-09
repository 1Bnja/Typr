import { SAMPLE_TEXTS } from '../constants'

function getSampleText(language, difficulty) {
  const options = SAMPLE_TEXTS[language] ?? SAMPLE_TEXTS.spa
  const content = options[Math.floor(Math.random() * options.length)]
  return { id: null, content, language, difficulty, idealTimeMs: null }
}

export async function getRandomText({ language, difficulty }) {
  const params = new URLSearchParams({ language, difficulty })
  try {
    const response = await fetch(`/api/v1/texts/random?${params}`)
    if (!response.ok) throw new Error('Text not available')
    return await response.json()
  } catch {
    return getSampleText(language, difficulty)
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
