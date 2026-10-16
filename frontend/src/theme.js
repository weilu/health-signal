import { createTheme } from '@mui/material/styles'
import { deepmerge } from '@mui/utils'

// Defaults every adopter inherits; branding.theme overrides them.
const BASE = {
  palette: {
    primary: { main: '#44617a' },
    // Fixed-order categorical palette (dataviz reference; CVD/contrast-checked on #fff, #FBFAF6, #121212).
    chart: {
      light: ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948'],
      dark: ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767'],
    },
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

// Merge before createTheme so overridden colours re-derive their shades. Malformed config throws,
// re-raised with its value so it's debuggable.
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
