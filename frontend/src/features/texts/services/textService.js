async function postText(path, body, token) {
  const response = await fetch(`/api/v1/texts${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  })
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = data?.detail
    throw new Error(
      typeof detail === 'string'
        ? detail
        : detail?.message || `Error del servidor (${response.status})`,
    )
  }
  return data
}

export const generateTexts = (token) =>
  postText('/generate', undefined, token)

export const saveTexts = (phrases, token) =>
  postText('/save', { phrases }, token)
