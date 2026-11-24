const API = import.meta.env.VITE_API_URL || ''

export async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  const body = await response.text()
  let data
  try {
    data = body ? JSON.parse(body) : {}
  } catch {
    const message = response.ok
      ? 'The API returned an unexpected response. Check the Vite proxy and Flask URL.'
      : `API request failed (${response.status}). Check the Flask server and Vite proxy.`
    throw new Error(message)
  }
  if (!response.ok) throw new Error(data.error || `API request failed (${response.status}).`)
  return data
}
