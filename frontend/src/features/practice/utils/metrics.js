// Una "palabra" estándar son 5 caracteres, así el PPM no depende del largo de cada palabra.
const CHARS_PER_WORD = 5

export function countCorrectChars(typed, text) {
  let correct = 0
  for (let i = 0; i < typed.length; i++) {
    if (typed[i] === text[i]) correct++
  }
  return correct
}

export function calculatePpm(correctChars, elapsedMs) {
  if (elapsedMs <= 0) return 0
  const minutes = elapsedMs / 60000
  return Math.round(correctChars / CHARS_PER_WORD / minutes)
}

export function calculatePrecision(keystrokes, errors) {
  if (keystrokes === 0) return 100
  const precision = ((keystrokes - errors) / keystrokes) * 100
  return Math.round(precision * 10) / 10
}

export function getSpeedUnit(language) {
  return language === 'spa' ? 'PPM' : 'WPM'
}

export function calculateScore(ppm, precision) {
  return Math.round(ppm * (precision / 100))
}

export function formatTime(ms) {
  const totalSeconds = Math.floor(ms / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}
