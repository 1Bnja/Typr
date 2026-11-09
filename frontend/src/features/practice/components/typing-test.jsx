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
  getSpeedUnit,
} from '../utils/metrics'

// Teclas que moverían el cursor dentro del input y desordenarían la comparación.
const BLOCKED_KEYS = ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End', 'Enter']

const TypingTest = ({ text, onFinish, onCancel, onFocusChange }) => {
  const [typed, setTyped] = useState('')
  const [startTime, setStartTime] = useState(null)
  const [now, setNow] = useState(null)
  const [keystrokes, setKeystrokes] = useState(0)
  const [errors, setErrors] = useState(0)
  const [isFocused, setIsFocused] = useState(false)
  const [composition, setComposition] = useState(null)
  const inputRef = useRef(null)
  const finishedRef = useRef(false)
  const focusMode = startTime !== null && isFocused

  useEffect(() => {
    onFocusChange(focusMode)
    return () => onFocusChange(false)
  }, [focusMode, onFocusChange])

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
    if (finishedRef.current) return
    // Las tildes se evalúan al terminar de componer el carácter.
    if (e.nativeEvent.isComposing) {
      setComposition(e.target.value)
      return
    }
    const value = e.target.value.normalize('NFC')
    if (value.length > content.length || value === typed) return
    if (value.length > typed.length && !value.startsWith(typed)) return
    if (value.length < typed.length && !typed.startsWith(value)) return
    if (value.length === typed.length) return
    if (!startTime && value.length === 0) return

    const time = Date.now()
    const start = startTime ?? time
    if (startTime === null) setStartTime(time)
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

    const isFinished = value.length === content.length && !e.nativeEvent.isComposing
    if (isFinished) {
      finishedRef.current = true
      const timeMs = Math.max(1, time - start)
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
    if (e.nativeEvent.isComposing) return
    if (e.key === 'Escape') {
      e.preventDefault()
      inputRef.current.blur()
      return
    }
    if (BLOCKED_KEYS.includes(e.key)) e.preventDefault()
  }

  const moveCursorToEnd = (e) => {
    if (composition !== null) return
    const input = e.target
    input.setSelectionRange(input.value.length, input.value.length)
  }

  return (
    <div className="practice-session">
      <div className="practice-metrics">
        <div className="practice-live-metrics practice-focus-fade" inert={focusMode} aria-hidden={focusMode || undefined}>
          <Stat label={getSpeedUnit(text.language)} value={ppm} />
          <Stat label="Accuracy" value={`${precision}%`} />
        </div>
        <p className="practice-timer"><span className="sr-only">Elapsed time </span>{formatTime(elapsedMs)}</p>
      </div>

      <div className="practice-typing-area">
        <TypingText text={content} typed={typed} />
        <textarea
          ref={inputRef}
          className="practice-input"
          aria-label="Type the text"
          aria-describedby="practice-instructions practice-text"
          value={composition ?? typed}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onPaste={(e) => e.preventDefault()}
          onDrop={(e) => e.preventDefault()}
          onSelect={moveCursorToEnd}
          onCompositionStart={() => setComposition(typed)}
          onCompositionEnd={(e) => {
            setComposition(null)
            handleChange(e)
          }}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="off"
          spellCheck={false}
        />
      </div>
      <div className="practice-test-footer practice-focus-fade" aria-hidden={focusMode || undefined}>
        <p id="practice-instructions" className="practice-focus-status">
          <span className={isFocused ? 'practice-status-dot practice-status-dot--active' : 'practice-status-dot'} aria-hidden="true" />
          {!isFocused ? 'Click the text to keep typing.' : startTime === null ? 'Ready when you are.' : 'Test in progress.'}
        </p>
        <p className="practice-character-count">{typed.length} / {content.length} characters</p>
      </div>

      <div className="practice-session-actions practice-focus-fade" inert={focusMode} aria-hidden={focusMode || undefined}>
        <Button variant="ghost" onClick={onCancel}>Change settings</Button>
        <p><kbd>Backspace</kbd> to correct · <kbd>Esc</kbd> to leave focus mode</p>
      </div>
    </div>
  )
}

export default TypingTest
