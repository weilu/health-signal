import { Navigate } from 'react-router-dom'
import { Box, CircularProgress, Alert } from '@mui/material'
import { useTranslation } from 'react-i18next'

// A 401 is the only lost-session signal (httpOnly cookie), so the redirect reacts to the fetch.
// Cached data beats a later error: a failed background refetch mustn't blank a working view.
export function ResourceBoundary({ query, children }) {
  const { t } = useTranslation()
  if (query.error?.status === 401) return <Navigate to="/login" replace />
  if (query.data !== undefined) return children(query.data)
  if (query.isPending) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
        <CircularProgress aria-label={t('app.loading')} />
      </Box>
    )
  }
  return <Alert severity="error">{t('app.error')}</Alert>
}
