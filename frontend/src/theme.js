import { createTheme } from '@mui/material/styles'

export function buildTheme(branding = {}) {
  const t = branding.theme || {}
  const mode = t.mode === 'dark' ? 'dark' : 'light'
  // Only a string primary is valid; a non-string (number/object) or bad color from config must not
  // crash createTheme and blank the whole SPA — fall back to defaults on any malformed value.
  const primary = typeof t.primary === 'string' ? { primary: { main: t.primary } } : {}
  try {
    return createTheme({ palette: { mode, ...primary } })
  } catch {
    return createTheme({ palette: { mode } })
  }
}
