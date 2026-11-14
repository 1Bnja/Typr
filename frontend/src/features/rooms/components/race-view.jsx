import { useCallback, useEffect, useRef, useState } from 'react'
import Stat from '../../practice/components/stat'
import { calculatePpm, calculatePrecision, formatTime, getSpeedUnit } from '../../practice/utils/metrics'
import RaceTrack from './race-track'
import RaceTyping from './race-typing'
import { PROGRESS_INTERVAL_MS } from '../constants'
import { initialRaceInput } from '../utils/race-input'

const progressKey = ({ typed, errors }) => `${typed}:${errors}`

const RaceView = ({ race, userId, send, focusMode, onFocusChange }) => {
  const { content, language } = race.text
  const [own, setOwn] = useState(() => initialRaceInput(race.you.typed, race.you.errors))
  const [elapsedMs, setElapsedMs] = useState(0)
  const [finishedMs, setFinishedMs] = useState(() => {
    if (race.you.typed !== content.length) return null
    return Math.max(1, race.you.finishedMs ?? Date.now() - race.startedAt)
  })
  const ownRef = useRef(own)
  const typingInputRef = useRef(null)
  // Lo que el servidor ya conoce: al retomar tras recargar es el avance previo.
  const sentRef = useRef(progressKey(race.you))
  const finished = own.typed === content.length

  const flush = useCallback(() => {
    const key = progressKey(ownRef.current)
    if (sentRef.current === key) return
    const { typed, errors } = ownRef.current
    // Si el socket está reconectando no se marca como enviado: se reintenta.
    if (send({ type: 'progress', typed, errors })) sentRef.current = key
  }, [send])

  useEffect(() => {
    // El avance viaja por intervalos, no en cada tecla.
    const progressTimer = setInterval(flush, PROGRESS_INTERVAL_MS)
    const tick = () => setElapsedMs(Date.now() - race.startedAt)
    const clock = setInterval(tick, 250)
    tick()
    return () => {
      clearInterval(progressTimer)
      clearInterval(clock)
    }
  }, [flush, race.startedAt])

  useEffect(() => {
    if (!focusMode) return
    const leaveFocus = (event) => {
      if (event.key === 'Escape' && !event.isComposing) onFocusChange(false)
    }
    window.addEventListener('keydown', leaveFocus)
    return () => window.removeEventListener('keydown', leaveFocus)
  }, [focusMode, onFocusChange])

  const handleInput = useCallback((next) => {
    ownRef.current = next
    setOwn(next)
    // El reloj de la ronda sigue para los demás, pero el tiempo propio se congela.
    if (next.typed === content.length) {
      setFinishedMs(Math.max(1, Date.now() - race.startedAt))
      flush()
    }
  }, [content.length, flush, race.startedAt])

  const timeLeftMs = Math.max(0, race.timeLimitMs - elapsedMs)
  const players = race.players.map((player) => (player.userId === userId
    ? { ...player, progress: own.typed / content.length, finished }
    : player))

  return (
    <div className="race" data-focus={focusMode}>
      <div className="practice-metrics">
        <div className={`practice-live-metrics ${finished ? '' : 'practice-focus-fade'}`}
          aria-hidden={(focusMode && !finished) || undefined}>
          <Stat label={getSpeedUnit(language)} value={calculatePpm(own.typed, finishedMs ?? elapsedMs)} />
          <Stat label="Accuracy" value={`${calculatePrecision(own.typed + own.errors, own.errors)}%`} />
        </div>
        <div className="race-controls">
          <p className="practice-timer">
            <span className="sr-only">Time left </span>
            {formatTime(Math.ceil(timeLeftMs / 1000) * 1000)}
          </p>
          <button type="button" className="race-focus-toggle" aria-pressed={focusMode}
            title={focusMode ? 'Exit focus mode (Esc)' : 'Enter focus mode'}
            onPointerDown={(event) => {
              if (typingInputRef.current === document.activeElement) event.preventDefault()
            }}
            onClick={() => onFocusChange(!focusMode)}>
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              {focusMode
                ? <path d="M4 9h5V4m6 0v5h5M4 15h5v5m6 0v-5h5" />
                : <path d="M4 9V4h5m6 0h5v5M4 15v5h5m6 0h5v-5" />}
            </svg>
            Focus
          </button>
        </div>
      </div>

      {finished ? (
        <p className="race-finished" role="status">You finished! Waiting for the other players…</p>
      ) : (
        <>
          <RaceTyping content={content} initial={own} onInput={handleInput} inputRef={typingInputRef} />
          <div className="practice-test-footer">
            <p id="race-instructions" className="race-blocked" role="status" data-blocked={own.wrong !== null}>
              {own.wrong !== null
                ? 'Mistake: press Backspace to fix it before you can keep going.'
                : 'A mistake stops your cursor until you fix it.'}
            </p>
            <p className="practice-character-count">{own.typed} / {content.length} characters</p>
          </div>
        </>
      )}
      <RaceTrack players={players} userId={userId} />
    </div>
  )
}

export default RaceView
