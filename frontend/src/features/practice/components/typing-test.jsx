import { useCallback, useEffect, useRef, useState } from 'react'
import Button from '../../../components/button'
import TypingText from './typing-text'
import Stat from './stat'
import { addSpeedSample } from '../utils/speed-history'
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
  const [hasStarted, setHasStarted] = useState(false)
  const [stats, setStats] = useState({ typed: '', keystrokes: 0, errors: 0, elapsedMs: 0 })
  const [isFocused, setIsFocused] = useState(false)
  const inputRef = useRef(null)
  const textRef = useRef(null)
  const compositionRef = useRef(false)
  const sessionRef = useRef({ typed: '', startTime: null, keystrokes: 0, errors: 0 })
  const finishedRef = useRef(false)
  const speedHistoryRef = useRef([])
  const focusMode = hasStarted && isFocused

  const updateStats = useCallback(() => {
    const session = sessionRef.current
    setStats({ ...session, elapsedMs: session.startTime === null ? 0 : Date.now() - session.startTime })
  }, [])

  useEffect(() => {
    onFocusChange(focusMode)
    return () => onFocusChange(false)
  }, [focusMode, onFocusChange])

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  useEffect(() => {
    if (!hasStarted) return
    const interval = setInterval(() => {
      if (finishedRef.current) return
      const session = sessionRef.current
      addSpeedSample(speedHistoryRef.current, session.typed, text.content, Date.now() - session.startTime, session.errors)
      updateStats()
    }, 1000)
    return () => clearInterval(interval)
  }, [hasStarted, updateStats, text.content])

  const content = text.content
  const { typed, keystrokes, errors, elapsedMs } = stats
  const ppm = calculatePpm(countCorrectChars(typed, content), elapsedMs)
  const precision = calculatePrecision(keystrokes, errors)

  const handleChange = (e) => {
    if (finishedRef.current) return
    // Las tildes se muestran al componer, pero se cuentan al confirmar el carácter.
    if (compositionRef.current || e.nativeEvent.isComposing) {
      textRef.current.updateInput(e.target.value.normalize('NFC').slice(0, content.length))
      return
    }
    const session = sessionRef.current
    const value = e.target.value.normalize('NFC')
    if (value.length > content.length || value === session.typed ||
      (value.length > session.typed.length && !value.startsWith(session.typed)) ||
      (value.length < session.typed.length && !session.typed.startsWith(value)) ||
      value.length === session.typed.length) {
      e.target.value = session.typed
      textRef.current.updateInput(session.typed)
      return
    }

    const time = Date.now()
    if (session.startTime === null) {
      session.startTime = time
      setHasStarted(true)
    }

    // El texto y el cursor responden directamente, sin esperar un render por tecla.
    textRef.current.updateInput(value)
    for (let i = session.typed.length; i < value.length; i++) {
      session.keystrokes++
      if (value[i] !== content[i]) session.errors++
    }
    session.typed = value
    if (e.target.value !== value) e.target.value = value

    if (value.length === content.length) {
      finishedRef.current = true
      const timeMs = Math.max(1, time - session.startTime)
      const finalPpm = calculatePpm(countCorrectChars(value, content), timeMs)
      const finalPrecision = calculatePrecision(session.keystrokes, session.errors)
      addSpeedSample(speedHistoryRef.current, value, content, timeMs, session.errors)
      onFinish({
        timeMs,
        typed: value,
        keystrokes: session.keystrokes,
        errors: session.errors,
        // PPM/precisión/score locales solo para mostrar al instante; el
        // servidor recalcula y sus valores reemplazan a estos al guardar.
        ppm: finalPpm,
        precisionPct: finalPrecision,
        score: calculateScore(finalPpm, finalPrecision),
        progress: 1,
        speedHistory: [...speedHistoryRef.current],
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
    if (compositionRef.current) return
    const input = e.target
    const end = input.value.length
    if (input.selectionStart !== end || input.selectionEnd !== end) input.setSelectionRange(end, end)
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
        <TypingText ref={textRef} text={content} isFocused={isFocused} isActive={focusMode} />
        <textarea
          ref={inputRef}
          className="practice-input"
          aria-label="Type the text"
          aria-describedby="practice-instructions practice-text"
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onPaste={(e) => e.preventDefault()}
          onDrop={(e) => e.preventDefault()}
          onSelect={moveCursorToEnd}
          onCompositionStart={() => { compositionRef.current = true }}
          onCompositionEnd={(e) => {
            compositionRef.current = false
            handleChange(e)
          }}
          onFocus={() => setIsFocused(true)}
          onBlur={() => {
            setIsFocused(false)
            updateStats()
          }}
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="off"
          spellCheck={false}
        />
      </div>
      <div className="practice-test-footer practice-focus-fade" aria-hidden={focusMode || undefined}>
        <p id="practice-instructions" className="practice-focus-status">
          <span className={isFocused ? 'practice-status-dot practice-status-dot--active' : 'practice-status-dot'} aria-hidden="true" />
          {!isFocused ? 'Click the text to keep typing.' : !hasStarted ? 'Ready when you are.' : 'Test in progress.'}
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
