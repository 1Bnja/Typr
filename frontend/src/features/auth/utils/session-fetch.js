export const SESSION_REJECTED = 'typr:session-rejected'

export async function sessionFetch(token, url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: { ...options.headers, Authorization: `Bearer ${token}` },
    })
    if (response.status === 401 && !options.signal?.aborted && typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent(SESSION_REJECTED, { detail: token }))
    }
    return response
}
