// What a TanStack query should render as. Cached data beats a later error: a failed background
// refetch (e.g. a server restart) must not replace a working view. A 401 still means the session is gone.
export function boundaryState(query) {
  if (query.error?.status === 401) return 'unauth'
  if (query.data !== undefined) return 'ok'
  if (query.isPending) return 'loading'
  return 'error'
}
