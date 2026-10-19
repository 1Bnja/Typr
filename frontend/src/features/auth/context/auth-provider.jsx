import { createContext, useContext, useState, useEffect } from 'react';
import { login as loginRequest } from '../services/authService';
import { clearSession, readSession, saveSession } from '../utils/session';

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
    const stored = readSession()
    const [user, setUser] = useState(stored.user)
    const [token, setToken] = useState(stored.token)
    const [status, setStatus] = useState(stored.token ? 'loading' : 'unauthenticated')

    useEffect(() => {
        if (!token) return
        let cancelled = false

        fetch('/api/v1/users/me', {
            headers: { Authorization: `Bearer ${token}` },
        })
        .then(async (response) => {
            if (!response.ok) throw new Error('Session expired')
            return response.json()
        })
        .then((me) => {
            if (cancelled) return
            setUser(me)
            setStatus('authenticated')
        })
        .catch(() => {
            if (cancelled) return
            setUser(null)
            setToken(null)
            setStatus('unauthenticated')
        })

    return () => {
        cancelled = true
    }
}, [token])

async function signIn({ email, password }) {
    const data = await loginRequest({ email, password })
    saveSession(data.token, data.user)
    setToken(data.token)
    setUser(data.user)
    setStatus('authenticated')
}

function signOut() {
    clearSession()
    setToken(null)
    setUser(null)
    setStatus('unauthenticated')
}

return (
    <AuthContext.Provider value={{ user, token, status, signIn, signOut }}>
        {children}
    </AuthContext.Provider>
    )
}

export function useAuth() {
    const context = useContext(AuthContext)
    if (!context) throw new Error('useAuth must be used within an AuthProvider')
    return context
}