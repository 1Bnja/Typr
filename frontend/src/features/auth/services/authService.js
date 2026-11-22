export async function login({ email, password }) {
    const response = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
    })

    const data = await response.json().catch(() => null)
    if (!response.ok) {
        throw new Error(response.status === 401
            ? 'Email or password is incorrect. Check both and try again.'
            : 'Could not sign in. Please try again.')
    }
    return data
}

const DUPLICATE_EMAIL_MESSAGE = 'Este correo ya está en uso'

export class DuplicateEmailError extends Error {
    constructor() {
        super(DUPLICATE_EMAIL_MESSAGE)
    }
}

export class RegistrationFieldError extends Error {
    constructor(fields) {
        super('Error al registrar usuario')
        this.fields = fields
    }
}

function registrationLengthErrors(detail) {
    const fields = {}
    if (!Array.isArray(detail)) return fields

    for (const issue of detail) {
        if (!Array.isArray(issue?.loc) || issue.loc.length !== 2 || issue.loc[0] !== 'body') continue
        const field = issue.loc[1]
        if (field === 'username' && issue.type === 'string_too_short') {
            fields.username = 'Username must be at least 3 characters.'
        } else if (field === 'username' && issue.type === 'string_too_long') {
            fields.username = 'Username must be at most 20 characters.'
        } else if (field === 'password' && issue.type === 'string_too_short') {
            fields.password = 'Password must be at least 8 characters.'
        }
    }
    return fields
}

export async function register({ username, email, password }) {
    const response = await fetch('/api/v1/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, email, password }),
    })
    const data = await response.json().catch(() => null)
    if (!response.ok) {
        const detail = data?.detail
        if (response.status === 409 && detail === DUPLICATE_EMAIL_MESSAGE) {
            throw new DuplicateEmailError()
        }
        if (response.status === 422) {
            const fields = registrationLengthErrors(detail)
            if (Object.keys(fields).length) throw new RegistrationFieldError(fields)
        }
        throw new Error(typeof detail === 'string' ? detail : 'Error al registrar usuario')
    }
    return data
}

export default { login, register }
