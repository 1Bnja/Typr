export async function getRandomText(token, { language, difficulty, previousId }) {
  const params = new URLSearchParams({ language, difficulty })
  if (previousId != null) params.set('excludeId', previousId)
  const response = await fetch(`/api/v1/texts/random?${params}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(typeof data?.detail === 'string' ? data.detail : 'No se pudo cargar una frase guardada. Inténtalo nuevamente.')
  }
  if (!Number.isInteger(data?.id) || !data?.content?.trim() || data.language !== language || data.difficulty !== difficulty) {
    throw new Error('La frase recibida no es válida. Inténtalo nuevamente.')
  }
  return data
}

export async function savePracticeMatch(token, { textId, difficulty, timeMs, typed, keystrokes, errors }) {
  const response = await fetch('/api/v1/matches/practice', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    // Solo señales crudas: el servidor calcula PPM, precisión y puntaje.
    body: JSON.stringify({ textId, difficulty, timeMs, typed, keystrokes, errors }),
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
