import { useEffect, useRef, useState } from 'react'

// Fetch once on mount -> { status: 'loading'|'ok'|'unauth'|'error', data }; a 401 maps to 'unauth'.
// Fetcher held in a ref so an inline function doesn't re-fire; `live` drops a post-unmount response.
export function useResource(fetcher) {
  const [state, setState] = useState({ status: 'loading' })
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher
  useEffect(() => {
    let live = true
    fetcherRef.current()
      .then((data) => { if (live) setState({ status: 'ok', data }) })
      .catch((e) => { if (live) setState({ status: e.status === 401 ? 'unauth' : 'error' }) })
    return () => { live = false }
  }, [])
  return state
}
