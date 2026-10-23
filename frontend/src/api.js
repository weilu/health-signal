// Non-OK throws with .status so callers can tell an expired session (401) from other failures.
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
export const fetchPeriods = () => apiGet('/api/periods')
export const fetchAssessments = (query) => apiGet('/api/assessments', query)
export const fetchThresholds = (query) => apiGet('/api/thresholds', query)
export const fetchPhases = (query) => apiGet('/api/phases', query)
export const fetchPhaseStreams = (query) => apiGet('/api/phase-streams', query)
