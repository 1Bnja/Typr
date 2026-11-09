import { useEffect, useRef, useState } from 'react'
import Button from '../../../components/button'
import TypingText from './typing-text'
import Stat from './stat'
import {
  calculatePpm,
  calculatePrecision,
  calculateScore,
  countCorrectChars,
  formatTime,
} from '../utils/metrics'

// Teclas que moverían el cursor dentro del input y desordenarían la comparación.
const BLOCKED_KEYS = ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End']

const TypingTest = ({ text, onFinish, onCancel }) => {
  const [typed, setTyped] = useState('')
  const [startTime, setStartTime] = useState(null)
  const [now, setNow] = useState(null)
  const [keystrokes, setKeystrokes] = useState(0)
  const [errors, setErrors] = useState(0)
  const [isFocused, setIsFocused] = useState(false)
  const inputRef = useRef(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  useEffect(() => {
    if (!startTime) return
    const interval = setInterval(() => setNow(Date.now()), 200)
    return () => clearInterval(interval)
  }, [startTime])

  const content = text.content
  const elapsedMs = startTime ? now - startTime : 0
  const ppm = calculatePpm(countCorrectChars(typed, content), elapsedMs)
  const precision = calculatePrecision(keystrokes, errors)

  const handleChange = (e) => {
    const value = e.target.value
    if (value.length > content.length) return

    const time = Date.now()
    const start = startTime ?? time
    if (!startTime) setStartTime(time)
    setNow(time)

    // Solo contamos caracteres nuevos; borrar no suma ni resta errores.
    let newKeystrokes = keystrokes
    let newErrors = errors
    for (let i = typed.length; i < value.length; i++) {
      newKeystrokes++
      if (value[i] !== content[i]) newErrors++
    }

    setTyped(value)
    setKeystrokes(newKeystrokes)
    setErrors(newErrors)

    const lastIndex = content.length - 1
    const isFinished = value.length === content.length && value[lastIndex] === content[lastIndex]
    if (isFinished) {
      const timeMs = time - start
      const finalPpm = calculatePpm(countCorrectChars(value, content), timeMs)
      const finalPrecision = calculatePrecision(newKeystrokes, newErrors)
      onFinish({
        timeMs,
        ppm: finalPpm,
        precisionPct: finalPrecision,
        score: calculateScore(finalPpm, finalPrecision),
        progress: 1,
      })
    }
  }

  const handleKeyDown = (e) => {
    if (BLOCKED_KEYS.includes(e.key)) e.preventDefault()
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-3 gap-3">
        <Stat label="PPM" value={ppm} />
        <Stat label="Precision" value={`${precision}%`} />
        <Stat label="Time" value={formatTime(elapsedMs)} />
      </div>

      <div
        className={`relative rounded-2xl border bg-white p-6 shadow-[0_3px_0_#e1e2dc] ${isFocused ? 'border-[#18a98a]' : 'border-[#e1e2dc]'}`}
      >
        <TypingText text={content} typed={typed} />
        <input
          ref={inputRef}
          className="absolute inset-0 h-full w-full cursor-text opacity-0"
          type="text"
          aria-label="Type the text"
          value={typed}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onPaste={(e) => e.preventDefault()}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="off"
          spellCheck={false}
        />
      </div>
      {!isFocused && (
        <p className="-mt-3 text-sm text-neutral-600">Click the text to keep typing.</p>
      )}

      <Button variant="secondary" onClick={onCancel} className="self-start">
        Change settings
      </Button>
    </div>
  )
}

export default TypingTest
