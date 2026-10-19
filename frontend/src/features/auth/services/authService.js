/**
 * Login a user
 */
export async function login({ email, password }) {
    const response = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
    })

    const data = await response.json().catch(() => null)
    if (!response.ok) {
        const detail = data?.detail
        throw new Error(typeof detail === 'string' ? detail : 'Error al iniciar sesión')
    }
    return data
}

/**
 * Register a new user
 */
export async function register({ username, email, password }) {
    const response = await fetch('/api/v1/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, email, password }),
    })
    const data = await response.json().catch(() => null)
    if (!response.ok) {
        const detail = data?.detail
        throw new Error(typeof detail === 'string' ? detail : 'Error al registrar usuario')
    }
    return data
}

export default { login, register }