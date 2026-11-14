import { useCallback, useEffect, useReducer, useRef, useState } from 'react'
import { CLOSE_REASONS } from '../constants'
import { roomSocketUrl } from '../services/rooms-service'
import { initialRoomState, roomReducer } from '../utils/room-state'

const MAX_RETRIES = 5

// Mantiene el socket de la sala: se autentica al abrir, traduce los mensajes
// al estado de la vista y reconecta si la conexión se cae sin motivo final.
export function useRoomSocket(code, token) {
  const [state, dispatch] = useReducer(roomReducer, initialRoomState)
  const [connection, setConnection] = useState({ status: 'connecting', closeCode: null })
  const socketRef = useRef(null)

  useEffect(() => {
    let active = true
    let retries = 0
    let timer = null

    const open = () => {
      const socket = new WebSocket(roomSocketUrl(code))
      socketRef.current = socket
      // El token va en el primer mensaje, no en la URL.
      socket.onopen = () => socket.send(JSON.stringify({ type: 'auth', token }))
      socket.onmessage = (event) => {
        if (!active) return
        retries = 0
        setConnection((current) => (current.status === 'open' ? current : { status: 'open', closeCode: null }))
        dispatch({ ...JSON.parse(event.data), receivedAt: Date.now() })
      }
      socket.onclose = (event) => {
        if (!active || socketRef.current !== socket) return
        if (event.code in CLOSE_REASONS || retries >= MAX_RETRIES) {
          setConnection({ status: 'closed', closeCode: event.code })
          return
        }
        retries += 1
        setConnection({ status: 'connecting', closeCode: null })
        timer = setTimeout(open, 1000 * retries)
      }
    }

    open()
    return () => {
      active = false
      clearTimeout(timer)
      socketRef.current?.close()
    }
  }, [code, token])

  const send = useCallback((message) => {
    const socket = socketRef.current
    if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(message))
  }, [])

  return { state, dispatch, send, connection }
}
