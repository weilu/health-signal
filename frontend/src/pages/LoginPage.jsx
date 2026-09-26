import { useState } from 'react'
import { Box, Paper, TextField, Button, Typography, Alert } from '@mui/material'
import { useTranslation } from 'react-i18next'

export default function LoginPage({ config }) {
  const { t } = useTranslation()
  const [error, setError] = useState(null)  // null | 'invalid' (401) | 'failed' (other/network)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setSubmitting(true)
    setError(false)
    const body = new URLSearchParams(new FormData(e.currentTarget))
    // POST via fetch (not a native form) so a 401 renders inline instead of replacing the SPA with
    // raw JSON. On success the server sets the cookie + 303s; redirect:'manual' surfaces that as an
    // opaqueredirect, and a full navigation to '/' loads the authenticated SPA (which fetches /api/config).
    const res = await fetch('/login', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
      redirect: 'manual',
    }).catch(() => null)
    if (res && (res.ok || res.type === 'opaqueredirect' || res.status === 303)) {
      window.location.assign('/')
      return
    }
    setSubmitting(false)
    setError(res && res.status === 401 ? 'invalid' : 'failed')  // only a 401 means bad credentials
  }

  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', mt: 6 }}>
      <Paper sx={{ p: 4, width: 360 }} elevation={2}>
        <Typography variant="h5" gutterBottom>{config.title}</Typography>
        <Typography variant="subtitle1" gutterBottom>{t('login.title')}</Typography>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{t(error === 'invalid' ? 'login.error' : 'login.failed')}</Alert>}
        <form onSubmit={handleSubmit}>
          <TextField name="email" type="email" label={t('login.email')} fullWidth required margin="normal" />
          <TextField name="password" type="password" label={t('login.password')} fullWidth required margin="normal" />
          <Button type="submit" variant="contained" fullWidth sx={{ mt: 2 }} disabled={submitting}>{t('login.submit')}</Button>
        </form>
      </Paper>
    </Box>
  )
}
