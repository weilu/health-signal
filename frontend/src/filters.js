// In the URL so a regional view is deep-linkable; an unknown value falls back to the default.
export function selectedLocation(filter, search) {
  if (!filter) return null
  const wanted = new URLSearchParams(search).get('location')
  return filter.options.some((o) => o.value === wanted) ? wanted : filter.default
}

export function withLocation(path, location) {
  return location ? `${path}?${new URLSearchParams({ location })}` : path
}

export function panelParams(query, location) {
  return { indicator: query.indicator, ...query.dimensions, ...(location ? { location } : {}) }
}
