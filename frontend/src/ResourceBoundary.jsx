import { Navigate } from 'react-router-dom'
import { Box, CircularProgress, Alert } from '@mui/material'
import { useTranslation } from 'react-i18next'

// Maps a TanStack query to UI (loading / 401 -> login / error) so pages don't each re-implement it.
// A 401 is the only signal of a lost session (httpOnly cookie), so the redirect reacts to the fetch.
export function ResourceBoundary({ query, children }) {
  const { t } = useTranslation()
  if (query.isPending) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
        <CircularProgress aria-label={t('app.loading')} />
      </Box>
    )
  }
  if (query.error?.status === 401) return <Navigate to="/login" replace />
  if (query.isError) return <Alert severity="error">{t('app.error')}</Alert>
  return children(query.data)
}
