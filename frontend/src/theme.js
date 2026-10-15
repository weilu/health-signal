import { createTheme } from '@mui/material/styles'
import { deepmerge } from '@mui/utils'

// Library base theme: the default identity every adopter inherits and can override via
// branding.theme. IBM Plex Sans (self-hosted, see main.jsx) reads as considered public-sector/
// technical rather than default Roboto; sentence-case buttons avoid MUI's dated ALL-CAPS. The
// default palette is a muted slate — a calm, neutral starting point, not MUI's bright blue — so an
// adopter that sets no colors still looks institutional.
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

// branding.theme is a MUI theme-options object, deep-merged over BASE (config wins) BEFORE
// createTheme runs, so an overridden palette color re-derives its light/dark variants from the new
// main (merging after createTheme would leave stale default-blue hover states). MUI's own schema +
// validation apply; a malformed theme throws by design, re-thrown with its config location + value
// so the failure is debuggable rather than a silently unthemed app.
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
