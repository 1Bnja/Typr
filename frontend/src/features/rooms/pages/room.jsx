import { useState } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../../auth'
import RoomLobby from '../components/room-lobby'
import { CLOSE_REASONS, settingLabel } from '../constants'
import { useRoomSocket } from '../hooks/use-room-socket'
import { closeRoom, kickMember, leaveRoom, updateRoom } from '../services/rooms-service'
import '../../practice/practice.css'
import '../../practice/records.css'
import '../rooms.css'

const RoomSession = ({ code, token, userId }) => {
  const navigate = useNavigate()
  const { state, dispatch, send, connection } = useRoomSocket(code, token)
  const [busy, setBusy] = useState(false)
  const [leaving, setLeaving] = useState(false)
  const [actionError, setActionError] = useState(null)
  const { room } = state

  const run = async (action, { exit = false } = {}) => {
    setBusy(true)
    setActionError(null)
    dispatch({ type: 'clear_error' })
    if (exit) setLeaving(true)
    try {
      await action()
      if (exit) navigate('/rooms', { replace: true })
    } catch (failure) {
      setLeaving(false)
      setActionError(failure)
    } finally {
      setBusy(false)
    }
  }

  if (leaving) return <p className="p-8 text-center text-neutral-600" role="status">Leaving the room…</p>

  if (connection.status === 'closed') {
    const expired = connection.closeCode === 4401
    return (
      <section className="practice rooms">
        <div className="records-feedback" role="alert">
          <h2>{CLOSE_REASONS[connection.closeCode] ?? 'The connection to the room was lost.'}</h2>
          <Link to={expired ? '/login' : '/rooms'} className="button button--primary">
            {expired ? 'Sign in' : 'Back to multiplayer'}
          </Link>
        </div>
      </section>
    )
  }

  if (!room) return <p className="p-8 text-center text-neutral-600" role="status">Connecting to the room…</p>

  return (
    <section className="practice rooms">
      <header className="practice-header">
        <h1>Race room</h1>
        <p>
          {['language', 'difficulty', 'rounds'].map((key) => settingLabel(key, room[key])).join(' · ')}
          {connection.status === 'connecting' && ' · Reconnecting…'}
        </p>
      </header>

      <RoomLobby
        room={room}
        userId={userId}
        error={state.error ?? actionError}
        busy={busy}
        onReady={(ready) => send({ type: 'ready', ready })}
        onStart={() => { dispatch({ type: 'clear_error' }); setActionError(null); send({ type: 'start' }) }}
        onUpdate={(changes) => run(() => updateRoom(token, code, changes))}
        onKick={(memberId) => run(() => kickMember(token, code, memberId))}
        onLeave={() => run(() => leaveRoom(token, code), { exit: true })}
        onClose={() => run(() => closeRoom(token, code), { exit: true })}
      />
    </section>
  )
}

const Room = () => {
  const { code } = useParams()
  const { status, token, user } = useAuth()

  if (status === 'loading') return <p className="p-8 text-center text-neutral-600">Loading…</p>
  if (status === 'unauthenticated') return <Navigate to="/login" replace />
  // La clave reinicia la sesión completa si se navega a otra sala.
  return <RoomSession key={code} code={code.toUpperCase()} token={token} userId={user.id} />
}

export default Room
