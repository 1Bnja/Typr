import { useEffect, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth'
import Button from '../../../components/button'
import RoomSettings from '../components/room-settings'
import { DEFAULT_SETTINGS, ROOM_CODE_LENGTH, ROOM_ERRORS, roomErrorMessage } from '../constants'
import { createRoom, getMyRoom, joinRoom } from '../services/rooms-service'
import '../../practice/practice.css'
import '../rooms.css'

const Rooms = () => {
  const { status, token } = useAuth()
  const navigate = useNavigate()
  const [checking, setChecking] = useState(true)
  const [settings, setSettings] = useState(DEFAULT_SETTINGS)
  const [code, setCode] = useState('')
  const [pending, setPending] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (status !== 'authenticated') return
    const controller = new AbortController()
    // Un usuario pertenece a una sola sala: si ya tiene una, va directo a ella.
    getMyRoom(token, controller.signal)
      .then((room) => {
        if (controller.signal.aborted) return
        if (room) navigate(`/rooms/${room.code}`, { replace: true })
        else setChecking(false)
      })
      .catch((failure) => {
        if (!controller.signal.aborted && failure.name !== 'AbortError') setChecking(false)
      })
    return () => controller.abort()
  }, [status, token, navigate])

  if (status === 'loading') return <p className="p-8 text-center text-neutral-600">Loading…</p>
  if (status === 'unauthenticated') return <Navigate to="/login" replace />
  if (checking) return <p className="p-8 text-center text-neutral-600" role="status">Looking for your room…</p>

  const enter = async (form, action) => {
    setPending(form)
    setError(null)
    try {
      const room = await action()
      navigate(`/rooms/${room.code}`)
    } catch (failure) {
      setError({ form, message: roomErrorMessage(failure) })
      setPending(null)
    }
  }

  const handleJoin = (event) => {
    event.preventDefault()
    if (code.length !== ROOM_CODE_LENGTH) {
      setError({ form: 'join', message: ROOM_ERRORS.room_not_found })
      return
    }
    enter('join', () => joinRoom(token, code))
  }

  const busy = pending !== null

  return (
    <section className="practice rooms">
      <header className="practice-header">
        <h1>Multiplayer</h1>
        <p>Race other typists on the same text, in real time. Create a room or join one with its code.</p>
      </header>

      <div className="rooms-entry">
        <form className="rooms-card" onSubmit={(event) => { event.preventDefault(); enter('create', () => createRoom(token, settings)) }}>
          <h2>Create a room</h2>
          <p className="rooms-card-note">You will be the host: you set the rules and start the race.</p>
          <RoomSettings
            settings={settings}
            disabled={busy}
            onChange={(key, value) => setSettings((current) => ({ ...current, [key]: value }))}
          />
          <div className="rooms-card-footer">
            <Button type="submit" variant="primary" isLoading={pending === 'create'} disabled={busy}>
              {pending === 'create' ? 'Creating…' : 'Create room'}
            </Button>
            {error?.form === 'create' && <p role="alert" className="practice-error">{error.message}</p>}
          </div>
        </form>

        <form className="rooms-card" onSubmit={handleJoin}>
          <h2>Join a room</h2>
          <p className="rooms-card-note">Ask the host for the {ROOM_CODE_LENGTH}-character code.</p>
          <label className="rooms-code-field">
            <span className="select-label">Room code</span>
            <input
              className="rooms-code-input"
              value={code}
              onChange={(event) => {
                setCode(event.target.value.replace(/[^a-z0-9]/gi, '').toUpperCase().slice(0, ROOM_CODE_LENGTH))
                setError(null)
              }}
              placeholder="ABC234"
              inputMode="text"
              autoComplete="off"
              autoCapitalize="characters"
              spellCheck={false}
              disabled={busy}
              aria-invalid={error?.form === 'join' || undefined}
              aria-describedby={error?.form === 'join' ? 'join-error' : undefined}
            />
          </label>
          <div className="rooms-card-footer">
            <Button type="submit" variant="secondary" isLoading={pending === 'join'} disabled={busy}>
              {pending === 'join' ? 'Joining…' : 'Join room'}
            </Button>
            {error?.form === 'join' && <p id="join-error" role="alert" className="practice-error">{error.message}</p>}
          </div>
        </form>
      </div>
    </section>
  )
}

export default Rooms
