export const MODE_LABELS = {
  singleplayer: 'Practice',
  multiplayer: 'Multiplayer',
}

const ORDINALS = { one: 'st', two: 'nd', few: 'rd', other: 'th' }
const pluralRules = new Intl.PluralRules('en', { type: 'ordinal' })

export const ordinal = (value) => `${value}${ORDINALS[pluralRules.select(value)]}`

export async function getMyStats(token, { offset = 0, limit = 10 } = {}, signal) {
  const params = new URLSearchParams({ offset, limit })
  const response = await fetch(`/api/v1/users/me/stats?${params}`, {
    headers: { Authorization: `Bearer ${token}` },
    signal,
  })
  if (!response.ok) throw new Error('Could not load your stats. Please try again.')
  return response.json()
}

// Puntos del gráfico: el número de partida sirve de eje X para que dos
// partidas del mismo día no se superpongan.
export function toTrendData(trend, total) {
  const first = total - trend.length + 1
  return trend.map((point, index) => ({
    match: first + index,
    finishedAt: point.finishedAt,
    mode: point.mode,
    ppm: point.ppm,
    precision: Number(point.precisionPct.toFixed(1)),
  }))
}

// Resumen en texto del gráfico, para lectores de pantalla y como titular.
export function describeTrend(trend) {
  if (trend.length === 0) return ''
  if (trend.length === 1) return `Your first match: ${trend[0].ppm} words per minute.`
  const first = trend[0].ppm
  const last = trend.at(-1).ppm
  const change = last - first
  if (change === 0) return `Over your last ${trend.length} matches your speed held steady at ${last} words per minute.`
  const direction = change > 0 ? 'up' : 'down'
  return `Over your last ${trend.length} matches your speed went ${direction} ${Math.abs(change)} words per minute, from ${first} to ${last}.`
}
