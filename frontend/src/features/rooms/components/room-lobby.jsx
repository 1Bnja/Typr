import { useState } from 'react'
import Button from '../../../components/button'
import RoomSettings from './room-settings'
import { SETTING_FIELDS, roomErrorMessage, settingLabel } from '../constants'
import { canStartRace } from '../utils/room-state'

const startHint = (room) => {
  if (room.members.length < 2) return 'Share the code: you need at least 2 players.'
  if (room.members.some((member) => !member.connected)) return 'Waiting for every player to connect.'
  return 'Waiting for every player to be ready.'
}

const RoomLobby = ({ room, userId, error, busy, onReady, onStart, onUpdate, onKick, onLeave, onClose }) => {
  const [copied, setCopied] = useState(false)
  const me = room.members.find((member) => member.id === userId)
  const isHost = room.hostId === userId
  const racing = room.status !== 'waiting'
  const startable = canStartRace(room)

  const copyCode = async () => {
    try {
      await navigator.clipboard.writeText(room.code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div className="room-lobby">
      <div className="room-code">
        <span className="room-code-label">Room code</span>
        <strong className="room-code-value" aria-label={`Room code ${room.code.split('').join(' ')}`}>{room.code}</strong>
        <Button variant="secondary" size="sm" onClick={copyCode}>{copied ? 'Copied' : 'Copy code'}</Button>
        <span className="sr-only" role="status">{copied ? 'Room code copied' : ''}</span>
      </div>

      <div className="room-columns">
        <section aria-labelledby="room-players">
          <h2 id="room-players" className="room-section-title">
            Players <span>{room.members.length} / 10</span>
          </h2>
          <ul className="room-members">
            {room.members.map((member) => (
              <li key={member.id} className="room-member" data-current={member.id === userId}>
                <span className="records-avatar" aria-hidden="true">{member.username.slice(0, 2).toUpperCase()}</span>
                <span className="room-member-name">
                  <span className="records-username" title={member.username}>{member.username}</span>
                  {member.id === userId && <span className="records-you">You</span>}
                  {member.isHost && <span className="room-badge">Host</span>}
                </span>
                <span className="room-member-status" data-state={!member.connected ? 'offline' : member.isHost || member.isReady ? 'ready' : 'waiting'}>
                  {!member.connected ? 'Offline' : member.isHost ? 'Hosting' : member.isReady ? 'Ready' : 'Not ready'}
                </span>
                {isHost && !member.isHost && !racing && (
                  <Button variant="ghost" size="sm" disabled={busy} onClick={() => onKick(member.id)} aria-label={`Remove ${member.username} from the room`}>
                    Remove
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="room-rules">
          <h2 id="room-rules" className="room-section-title">Rules</h2>
          {isHost && !racing ? (
            <RoomSettings settings={room} disabled={busy} onChange={(key, value) => onUpdate({ [key]: value })} />
          ) : (
            <dl className="room-rules">
              {SETTING_FIELDS.map(({ key, label }) => (
                <div key={key}>
                  <dt>{label}</dt>
                  <dd>{settingLabel(key, room[key])}</dd>
                </div>
              ))}
            </dl>
          )}
        </section>
      </div>

      <div className="room-actions">
        {racing ? (
          <p className="room-hint" role="status">A race is in progress. The next round is about to start.</p>
        ) : isHost ? (
          <>
            <Button variant="primary" disabled={!startable || busy} onClick={onStart}>Start race</Button>
            {!startable && <p className="room-hint">{startHint(room)}</p>}
          </>
        ) : (
          <>
            <Button variant={me?.isReady ? 'secondary' : 'primary'} aria-pressed={me?.isReady ?? false} disabled={busy} onClick={() => onReady(!me?.isReady)}>
              {me?.isReady ? 'Ready — tap to undo' : 'I am ready'}
            </Button>
            <p className="room-hint">{me?.isReady ? 'Waiting for the host to start the race.' : 'Tell the host you are ready to race.'}</p>
          </>
        )}
        {error && <p role="alert" className="practice-error">{roomErrorMessage(error)}</p>}
        <div className="room-exit">
          {isHost
            ? <Button variant="ghost" disabled={busy} onClick={onClose}>Close room</Button>
            : <Button variant="ghost" disabled={busy} onClick={onLeave}>Leave room</Button>}
        </div>
      </div>
    </div>
  )
}

export default RoomLobby
