import { createTheme } from '@mui/material/styles'
import { deepmerge } from '@mui/utils'

// Base theme every adopter inherits and overrides via branding.theme: IBM Plex Sans (self-hosted,
// see main.jsx), sentence-case buttons, muted-slate default primary.
const BASE = {
  palette: {
    primary: { main: '#44617a' },
  },
  typography: {
    fontFamily: "'IBM Plex Sans', system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    h1: { fontSize: '1.75rem', fontWeight: 600, lineHeight: 1.2 },
    h4: { fontSize: '1.375rem', fontWeight: 600 },
    h5: { fontSize: '1.25rem', fontWeight: 600 },
    h6: { fontSize: '1.125rem', fontWeight: 600 },
    subtitle2: { fontWeight: 600 },
    button: { fontWeight: 500, textTransform: 'none' },
  },
  shape: { borderRadius: 8 },
}

// Deep-merge branding.theme over BASE BEFORE createTheme so an overridden color re-derives its
// light/dark shades (merging after would keep stale defaults). Malformed config throws by design,
// re-thrown with its location + value so it's debuggable.
export function buildTheme(branding = {}) {
  const options = branding.theme || {}
  try {
    return createTheme(deepmerge(BASE, options))
  } catch (err) {
    throw new Error(
      `Invalid branding.theme in dashboard.yaml: ${err.message}\nProvided: ${JSON.stringify(options)}`,
      { cause: err },
    )
  }
}
