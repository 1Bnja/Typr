import { calculatePpm, countCorrectChars } from './metrics.js'

export function addSpeedSample(samples, typed, text, timeMs, errors) {
  if (timeMs <= 0) return
  const sample = { timeMs, ppm: calculatePpm(countCorrectChars(typed, text), timeMs), errors }
  const last = samples.at(-1)
  if (last?.timeMs > timeMs) return
  if (last?.timeMs === timeMs) samples[samples.length - 1] = sample
  else samples.push(sample)
}
