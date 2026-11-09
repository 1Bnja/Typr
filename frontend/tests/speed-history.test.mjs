import assert from 'node:assert/strict'
import test from 'node:test'
import { addSpeedSample } from '../src/features/practice/utils/speed-history.js'
import { calculatePpm, countCorrectChars } from '../src/features/practice/utils/metrics.js'

test('a pause lowers cumulative speed without adding mistakes', () => {
  const samples = []
  addSpeedSample(samples, 'casa ', 'casa mesa', 1000, 0)
  addSpeedSample(samples, 'casa ', 'casa mesa', 2000, 0)
  assert.deepEqual(samples, [
    { timeMs: 1000, ppm: 60, errors: 0 },
    { timeMs: 2000, ppm: 30, errors: 0 },
  ])
})

test('corrected mistakes stay in the history while speed uses current correct characters', () => {
  const samples = []
  addSpeedSample(samples, 'x', 'casa', 1000, 1)
  addSpeedSample(samples, 'c', 'casa', 2000, 1)
  assert.deepEqual(samples, [
    { timeMs: 1000, ppm: 0, errors: 1 },
    { timeMs: 2000, ppm: 6, errors: 1 },
  ])
})

test('the final sample records exact duration, including tests shorter than one second', () => {
  const samples = []
  const typed = 'casa'
  const timeMs = 750
  addSpeedSample(samples, typed, typed, timeMs, 0)
  assert.equal(samples.length, 1)
  assert.equal(samples[0].timeMs, timeMs)
  assert.equal(samples[0].ppm, calculatePpm(countCorrectChars(typed, typed), timeMs))
})

test('duplicate timestamps replace the sample and invalid times do not distort the timeline', () => {
  const samples = []
  addSpeedSample(samples, 'c', 'casa', 0, 0)
  addSpeedSample(samples, 'c', 'casa', 1000, 0)
  addSpeedSample(samples, 'ca', 'casa', 1000, 1)
  addSpeedSample(samples, '', 'casa', 500, 0)
  assert.deepEqual(samples, [{ timeMs: 1000, ppm: 24, errors: 1 }])
})
