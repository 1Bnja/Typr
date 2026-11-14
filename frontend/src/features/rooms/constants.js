import { DIFFICULTIES, LANGUAGES } from '../practice/constants.js'

export const ROOM_CODE_LENGTH = 6
export const PROGRESS_INTERVAL_MS = 200

export const ROOM_TYPES = [
  { value: 'private', label: 'Private' },
  { value: 'quick', label: 'Quick match' },
]

export const ROUND_OPTIONS = [1, 2, 3, 5, 10].map((rounds) => ({
  value: rounds,
  label: rounds === 1 ? '1 round' : `${rounds} rounds`,
}))

// Automático: el servidor usa 2 veces el tiempo ideal de cada texto. En la API
// viaja como null; aquí tiene un valor propio porque las opciones lo usan de clave.
export const AUTOMATIC_TIME_LIMIT = 'auto'

export const TIME_LIMIT_OPTIONS = [
  { value: AUTOMATIC_TIME_LIMIT, label: 'Automatic' },
  { value: 30, label: '30 s' },
  { value: 60, label: '1 min' },
  { value: 90, label: '1 min 30 s' },
  { value: 120, label: '2 min' },
  { value: 180, label: '3 min' },
  { value: 300, label: '5 min' },
]

export const DEFAULT_SETTINGS = {
  type: 'private',
  language: 'spa',
  difficulty: 'easy',
  rounds: 1,
  timeLimitS: null,
}

export const SETTING_FIELDS = [
  { key: 'type', label: 'Room type', options: ROOM_TYPES },
  { key: 'language', label: 'Language', options: LANGUAGES },
  { key: 'difficulty', label: 'Difficulty', options: DIFFICULTIES.map(({ value, label }) => ({ value, label })) },
  { key: 'rounds', label: 'Rounds', options: ROUND_OPTIONS },
  { key: 'timeLimitS', label: 'Time limit', options: TIME_LIMIT_OPTIONS },
]

export const settingLabel = (key, value) =>
  SETTING_FIELDS.find((field) => field.key === key).options
    .find((option) => option.value === (value ?? AUTOMATIC_TIME_LIMIT))?.label ?? String(value)

export const ROOM_ERRORS = {
  room_not_found: 'That room code is not valid.',
  room_full: 'That room is full.',
  room_in_progress: 'That room has a race in progress. Wait until its rounds finish.',
  already_in_room: 'You already belong to a room.',
  not_host: 'Only the host can do that.',
  not_member: 'You do not belong to this room.',
  member_not_found: 'That player is no longer in the room.',
  not_enough_players: 'You need at least 2 players to start.',
  players_not_ready: 'Every player must be connected and ready.',
  no_texts: 'There are no texts for this language and difficulty yet.',
}

export const roomErrorMessage = (error) =>
  ROOM_ERRORS[error?.code] ?? 'Something went wrong. Please try again.'

// Códigos de cierre del WebSocket tras los que no tiene sentido reconectar.
export const CLOSE_REASONS = {
  4401: 'Your session expired. Sign in again to rejoin the room.',
  4403: 'You do not belong to this room.',
  4404: 'This room was closed.',
  4409: 'You opened this room in another tab.',
  4410: 'You are no longer in this room.',
}
