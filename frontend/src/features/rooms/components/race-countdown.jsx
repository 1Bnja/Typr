import { useEffect, useState } from 'react'

const RaceCountdown = ({ seconds }) => {
  const [left, setLeft] = useState(seconds)

  useEffect(() => {
    // La cuenta solo anima: el texto llega cuando el servidor da la partida.
    const timer = setInterval(() => setLeft((current) => Math.max(1, current - 1)), 1000)
    return () => clearInterval(timer)
  }, [])

  return (
    <div className="race-countdown">
      <p className="race-countdown-number" role="timer" aria-live="assertive" aria-atomic="true">{left}</p>
      <p className="room-hint">Get ready. Everyone gets the same text when the count ends.</p>
    </div>
  )
}

export default RaceCountdown
