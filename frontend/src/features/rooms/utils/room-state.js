// Estado de la vista de sala, derivado de los mensajes del WebSocket.
// phase: 'lobby' | 'countdown' | 'racing' | 'results'

export const initialRoomState = {
  room: null,
  phase: 'lobby',
  countdown: null,
  race: null,
  results: null,
  error: null,
}

export function roomReducer(state, message) {
  switch (message.type) {
    case 'room_state': {
      // Si la sala volvió a espera con una carrera a medias, la partida se canceló.
      const aborted = message.room.status === 'waiting' && (state.phase === 'countdown' || state.phase === 'racing')
      return {
        ...state,
        room: message.room,
        ...(aborted ? { phase: 'lobby', countdown: null, race: null } : {}),
      }
    }
    case 'countdown':
      return {
        ...state,
        phase: 'countdown',
        countdown: { round: message.round, rounds: message.rounds, seconds: message.seconds },
        race: null,
        results: null,
        error: null,
      }
    case 'race_start':
      return {
        ...state,
        phase: 'racing',
        countdown: null,
        results: null,
        error: null,
        race: {
          round: message.round,
          rounds: message.rounds,
          text: message.text,
          timeLimitMs: message.timeLimitMs,
          // El reloj local arranca descontando lo que ya corrió en el servidor.
          startedAt: message.receivedAt - message.elapsedMs,
          players: message.players,
          you: message.you ?? { typed: 0, errors: 0 },
        },
      }
    case 'progress_update':
      if (!state.race) return state
      return {
        ...state,
        race: {
          ...state.race,
          players: state.race.players.map((player) =>
            player.userId === message.userId
              ? { ...player, progress: message.progress, finished: message.finished }
              : player),
        },
      }
    case 'race_end':
      return {
        ...state,
        phase: 'results',
        countdown: null,
        race: null,
        results: {
          round: message.round,
          rounds: message.rounds,
          results: message.results,
          nextRoundInS: message.nextRoundInS,
        },
      }
    case 'error':
      return { ...state, error: { code: message.code, detail: message.detail } }
    case 'dismiss_results':
      return { ...state, phase: 'lobby', results: null }
    case 'clear_error':
      return { ...state, error: null }
    default:
      return state
  }
}

export const canStartRace = (room) =>
  room.status === 'waiting'
  && room.members.length >= 2
  && room.members.every((member) => member.connected && (member.isReady || member.isHost))
