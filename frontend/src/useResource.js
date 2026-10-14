import { useEffect, useRef, useState } from 'react'

// Fetch once on mount, tracking the lifecycle as { status: 'loading'|'ok'|'unauth'|'error', data }.
// A 401 becomes 'unauth' so a shared boundary can redirect to login; other failures are 'error'. The
// fetcher is read through a ref so it runs exactly once even if the caller passes an inline function,
// and `live` drops a response that resolves after unmount.
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
