// Cached data beats a later error: a failed background refetch mustn't blank a working view.
export function boundaryState(query) {
  if (query.error?.status === 401) return 'unauth'
  if (query.data !== undefined) return 'ok'
  if (query.isPending) return 'loading'
  return 'error'
}
