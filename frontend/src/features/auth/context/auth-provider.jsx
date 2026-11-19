import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AuthContext } from './auth-context'
import { login } from '../services/authService'
import { clearSession, readSession, saveSession } from '../utils/session'
import { SESSION_REJECTED, sessionFetch } from '../utils/session-fetch'

const signedOut = { token: null, user: null, status: 'unauthenticated' }

async function validateSession(token, signal) {
    const response = await sessionFetch(token, '/api/v1/users/me', { signal, cache: 'no-store' })
    if (!response.ok) throw new Error('Session validation failed')
    return response.json()
}

export function AuthProvider({ children }) {
    const [{ token, user, status }, setSession] = useState(() => {
        const { token } = readSession()
        return { token, user: null, status: token ? 'loading' : 'unauthenticated' }
    })
    const [notice, setNotice] = useState(null)
    const [retry, setRetry] = useState(0)
    const active = useRef(token)
    const navigate = useNavigate()

    useEffect(() => {
        function onRejected({ detail: { token: rejectedToken, notice: rejectionNotice } }) {
            if (active.current !== rejectedToken) return
            active.current = null
            clearSession(rejectedToken)
            setSession(signedOut)
            setNotice(rejectionNotice ?? 'Tu sesión ya no es válida. Inicia sesión de nuevo')
            navigate('/login', { replace: true })
        }
        window.addEventListener(SESSION_REJECTED, onRejected)
        return () => window.removeEventListener(SESSION_REJECTED, onRejected)
    }, [navigate])

    useEffect(() => {
        if (!token) return
        const controller = new AbortController()
        const { signal } = controller
        const isCurrent = () => !signal.aborted && active.current === token

        validateSession(token, signal)
            .then((me) => {
                if (isCurrent()) setSession({ token, user: me, status: 'authenticated' })
            })
            .catch(() => {
                if (isCurrent()) setSession({ token, user: null, status: 'unavailable' })
            })
        return () => controller.abort()
    }, [token, retry])

    async function signIn({ email, password }) {
        const data = await login({ email, password })
        active.current = data.token
        saveSession(data.token, data.user)
        setNotice(null)
        setSession({ token: data.token, user: data.user, status: 'authenticated' })
    }

    function signOut() {
        const signedOutToken = active.current
        const attempt = Symbol()
        active.current = attempt
        clearSession(signedOutToken)
        setSession(signedOut)
        setNotice(null)
        navigate('/login', { replace: true })

        fetch('/api/v1/auth/logout', {
            method: 'POST',
            headers: { Authorization: `Bearer ${signedOutToken}` },
            keepalive: true,
            signal: AbortSignal.timeout(5000),
        }).then(response => {
            if (response.status !== 204 && response.status !== 401) throw new Error('Logout unconfirmed')
        }).catch(() => {
            if (active.current === attempt) setNotice('Signed out on this device. Server revocation could not be confirmed.')
        })
    }

    function retryValidation() {
        setSession({ token, user: null, status: 'loading' })
        setRetry(value => value + 1)
    }

    return (
        <AuthContext.Provider value={{ user, token, status, notice, retryValidation, signIn, signOut }}>
            {children}
        </AuthContext.Provider>
    )
}
