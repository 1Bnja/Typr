import { sessionFetch } from '../../auth/utils/session-fetch.js'

let lastNotice

export function createPracticeAttemptId() {
  // getRandomValues also works on the project's non-loopback HTTP deployment.
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

export function reportPracticeActivity(token) {
  const noticeId = Date.now()
  if (lastNotice?.token === token && noticeId - lastNotice.noticeId < 60_000) return
  lastNotice = { token, noticeId }
  // No queued retries: a later typing event may try again, but only the server can renew.
  void sessionFetch(token, '/api/v1/auth/practice-activity', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ noticeId }),
    signal: AbortSignal.timeout(5000),
  }).catch(() => {})
}

export async function getRandomText(token, { language, difficulty, previousId }) {
  const params = new URLSearchParams({ language, difficulty })
  if (previousId != null) params.set('excludeId', previousId)
  const response = await sessionFetch(token, `/api/v1/texts/random?${params}`)
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(typeof data?.detail === 'string' ? data.detail : 'No se pudo cargar una frase guardada. Inténtalo nuevamente.')
  }
  if (!Number.isInteger(data?.id) || !data?.content?.trim() || data.language !== language || data.difficulty !== difficulty) {
    throw new Error('La frase recibida no es válida. Inténtalo nuevamente.')
  }
  return data
}

export async function savePracticeMatch(token, { attemptId, textId, difficulty, timeMs, typed, keystrokes, errors }) {
  const response = await sessionFetch(token, '/api/v1/matches/practice', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    // Solo señales crudas: el servidor calcula PPM, precisión y puntaje.
    body: JSON.stringify({ attemptId, textId, difficulty, timeMs, typed, keystrokes, errors }),
    signal: AbortSignal.timeout(10000),
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
  const response = await sessionFetch(token, `/api/v1/matches/${path}?${params}`, {
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
