// The location the dashboard shows: ?location= when it's a configured option, else the default; null
// when no location filter is configured. The URL holds it so a regional view is deep-linkable.
export function selectedLocation(filter, search) {
  if (!filter) return null
  const wanted = new URLSearchParams(search).get('location')
  return filter.options.some((o) => o.value === wanted) ? wanted : filter.default
}

// A link that keeps the current location selection.
export function withLocation(path, location) {
  return location ? `${path}?${new URLSearchParams({ location })}` : path
}

// A panel's /api/data params: its indicator and dimension filters, plus the dashboard's location.
export function panelParams(query, location) {
  return { indicator: query.indicator, ...query.dimensions, ...(location ? { location } : {}) }
}
