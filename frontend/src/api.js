// Same-origin JSON GET. A non-OK response throws with .status so ResourceBoundary can tell an
// expired session (401 -> login) from other failures.
export async function apiGet(path, params = {}) {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null && v !== ''))
  const res = await fetch(qs.size ? `${path}?${qs}` : path, { credentials: 'same-origin' })
  if (!res.ok) {
    const e = new Error(`${path}: ${res.status}`)
    e.status = res.status
    throw e
  }
  return res.json()
}

export const fetchConfig = () => apiGet('/api/config')
export const fetchData = (query) => apiGet('/api/data', query)
