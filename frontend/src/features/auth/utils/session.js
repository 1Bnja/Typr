const TOKEN_KEY = 'token';
const USER_KEY = 'user';

export function readSession() {
    const token = localStorage.getItem(TOKEN_KEY)
    const raw = localStorage.getItem(USER_KEY)
    if (!token || !raw) return { token: null, user: null }
    try {
        return { token, user: JSON.parse(raw) }
    } catch {
        return { token: null, user: null }
    }
}

export function saveSession(token, user) {
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function clearSession() {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
}