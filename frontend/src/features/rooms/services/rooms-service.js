export class RoomRequestError extends Error {
  constructor(code, message, status) {
    super(message)
    this.name = 'RoomRequestError'
    this.code = code
    this.status = status
  }
}

async function request(token, path = '', { method = 'GET', body, signal } = {}) {
  const response = await fetch(`/api/v1/rooms${path}`, {
    method,
    signal,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body ? { 'Content-Type': 'application/json' } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (response.status === 204) return null
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    // La API identifica cada rechazo con un código además del mensaje.
    const detail = data?.detail
    throw new RoomRequestError(detail?.code ?? 'unknown', detail?.message ?? 'Request failed', response.status)
  }
  return data
}

export const getMyRoom = (token, signal) => request(token, '/me', { signal })
export const createRoom = (token, settings) => request(token, '', { method: 'POST', body: settings })
export const joinRoom = (token, code) => request(token, `/${encodeURIComponent(code)}/join`, { method: 'POST' })
export const updateRoom = (token, code, changes) => request(token, `/${code}`, { method: 'PATCH', body: changes })
export const leaveRoom = (token, code) => request(token, `/${code}/leave`, { method: 'POST' })
export const kickMember = (token, code, memberId) => request(token, `/${code}/members/${memberId}`, { method: 'DELETE' })
export const closeRoom = (token, code) => request(token, `/${code}`, { method: 'DELETE' })

export function roomSocketUrl(code, location = window.location) {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${location.host}/api/v1/ws/rooms/${code}`
}
