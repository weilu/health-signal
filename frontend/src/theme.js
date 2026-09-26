import { createTheme } from '@mui/material/styles'

export function buildTheme(branding = {}) {
  const t = branding.theme || {}
  return createTheme({
    palette: {
      mode: t.mode || 'light',
      ...(t.primary ? { primary: { main: t.primary } } : {}),
    },
  })
}
