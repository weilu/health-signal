import { Navigate } from 'react-router-dom'
import { Box, CircularProgress, Alert } from '@mui/material'
import { useTranslation } from 'react-i18next'

// Map a useResource state to UI so pages don't each re-implement loading / 401-redirect / error.
// Auth is a server cookie the client can't read, so 'unauth' is only known from a 401 response — the
// login redirect therefore reacts to the fetch here, not in a pre-emptive route guard that would
// have to probe (and double-fetch) to learn the same thing.
export function ResourceBoundary({ state, children }) {
  const { t } = useTranslation()
  if (state.status === 'loading') {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
        <CircularProgress aria-label={t('app.loading')} />
      </Box>
    )
  }
  if (state.status === 'unauth') return <Navigate to="/login" replace />
  if (state.status === 'error') return <Alert severity="error">{t('app.error')}</Alert>
  return children(state.data)
}
