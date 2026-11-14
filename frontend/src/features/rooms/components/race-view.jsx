import { useCallback, useEffect, useRef, useState } from 'react'
import Stat from '../../practice/components/stat'
import { calculatePpm, calculatePrecision, formatTime, getSpeedUnit } from '../../practice/utils/metrics'
import RaceTrack from './race-track'
import RaceTyping from './race-typing'
import { PROGRESS_INTERVAL_MS } from '../constants'
import { initialRaceInput } from '../utils/race-input'

const progressKey = ({ typed, errors }) => `${typed}:${errors}`

const RaceView = ({ race, userId, send }) => {
  const { content, language } = race.text
  const [own, setOwn] = useState(() => initialRaceInput(race.you.typed, race.you.errors))
  const [elapsedMs, setElapsedMs] = useState(0)
  const ownRef = useRef(own)
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

  const handleInput = useCallback((next) => {
    ownRef.current = next
    setOwn(next)
    // La llegada se informa de inmediato: de ella depende la posición.
    if (next.typed === content.length) flush()
  }, [content.length, flush])

  const timeLeftMs = Math.max(0, race.timeLimitMs - elapsedMs)
  const players = race.players.map((player) => (player.userId === userId
    ? { ...player, progress: own.typed / content.length, finished }
    : player))

  return (
    <div className="race">
      <div className="practice-metrics">
        <div className="practice-live-metrics">
          <Stat label={getSpeedUnit(language)} value={calculatePpm(own.typed, elapsedMs)} />
          <Stat label="Accuracy" value={`${calculatePrecision(own.typed + own.errors, own.errors)}%`} />
        </div>
        <p className="practice-timer">
          <span className="sr-only">Time left </span>
          {formatTime(Math.ceil(timeLeftMs / 1000) * 1000)}
        </p>
      </div>

      <RaceTrack players={players} userId={userId} />

      {finished ? (
        <p className="race-finished" role="status">You finished! Waiting for the other players…</p>
      ) : (
        <>
          <RaceTyping content={content} initial={own} onInput={handleInput} />
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
    </div>
  )
}

export default RaceView
