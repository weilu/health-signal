import { createTheme } from '@mui/material/styles'

// branding.theme is a MUI theme-options object, handed straight to createTheme (MUI's own schema and
// validation). Malformed config throws by design; re-thrown with its location + value so the failure
// is debuggable rather than a silently unthemed app.
export function buildTheme(branding = {}) {
  const options = branding.theme || {}
  try {
    return createTheme(options)
  } catch (err) {
    throw new Error(
      `Invalid branding.theme in dashboard.yaml: ${err.message}\nProvided: ${JSON.stringify(options)}`,
      { cause: err },
    )
  }
}
