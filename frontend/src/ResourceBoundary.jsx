import { Navigate } from 'react-router-dom'
import { Box, CircularProgress, Alert } from '@mui/material'
import { useTranslation } from 'react-i18next'

// Maps a useResource state to UI (loading / 401->login / error) so pages don't each re-implement it.
// 'unauth' only comes from a 401 (httpOnly session isn't client-readable), so the redirect reacts to
// the fetch here rather than a pre-emptive guard that would double-fetch.
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
