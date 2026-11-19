const TOKEN_KEY = 'token';
const USER_KEY = 'user';

// The server issues JWT exp at the stored absolute deadline. This is only a
// local UX deadline; reading the claim does not validate or renew the session.
export function getAbsoluteDeadline(token) {
    try {
        const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
        const { exp } = JSON.parse(atob(payload))
        return Number.isSafeInteger(exp) && exp > 0 ? exp * 1000 : Infinity
    } catch {
        return Infinity
    }
}

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

export function clearSession(token) {
    if (localStorage.getItem(TOKEN_KEY) !== token) return
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
}
