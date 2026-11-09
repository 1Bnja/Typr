import { DIFFICULTIES } from '../constants.js'

export const RECORD_DIFFICULTIES = [...DIFFICULTIES, { value: 'expert', label: 'Expert' }]
export const RECORD_TIMEZONE = 'America/Santiago'

export function formatMatchDate(value) {
  return new Intl.DateTimeFormat('en', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    timeZone: RECORD_TIMEZONE,
  }).format(new Date(value))
}

export function getCurrentMonth() {
  const parts = new Intl.DateTimeFormat('en', {
    year: 'numeric', month: '2-digit', timeZone: RECORD_TIMEZONE,
  }).formatToParts(new Date())
  return `${parts.find((part) => part.type === 'year').value}-${parts.find((part) => part.type === 'month').value}`
}

export function formatMonth(value) {
  const [year, month] = value.split('-').map(Number)
  return new Intl.DateTimeFormat('en', { month: 'long', year: 'numeric', timeZone: 'UTC' })
    .format(new Date(Date.UTC(year, month - 1, 1)))
}

export function getDifficultyLabel(value) {
  return RECORD_DIFFICULTIES.find((option) => option.value === value)?.label ?? value
}
