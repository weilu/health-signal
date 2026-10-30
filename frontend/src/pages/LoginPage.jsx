import { useState } from 'react'
import { Paper, TextField, Button, Typography, Alert } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { LocaleToggle } from '../LocaleToggle.jsx'
import { siteTitle } from '../config.js'

export default function LoginPage({ config }) {
  const { t, i18n } = useTranslation()
  const [error, setError] = useState(null)  // null | 'invalid' (401) | 'failed' (other/network)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    const body = new URLSearchParams(new FormData(e.currentTarget))
    // fetch (not a native form) so a 401 shows inline, not a raw-JSON page. On success the 303 (seen
    // as opaqueredirect) lets us full-navigate to '/', loading the authenticated SPA.
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
    <Paper sx={{ p: 4, width: '100%', maxWidth: 400 }} elevation={2}>
      <Typography variant="h5" component="h1" gutterBottom>{siteTitle(config, i18n.resolvedLanguage)}</Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{t(error === 'invalid' ? 'login.error' : 'login.failed')}</Alert>}
      <form onSubmit={handleSubmit}>
        <TextField name="email" type="email" label={t('login.email')} fullWidth required margin="normal" autoComplete="email" autoFocus />
        <TextField name="password" type="password" label={t('login.password')} fullWidth required margin="normal" autoComplete="current-password" />
        <Button type="submit" variant="contained" fullWidth sx={{ mt: 2 }} disabled={submitting}>{t('login.submit')}</Button>
      </form>
      <LocaleToggle locales={config.locales} sx={{ mt: 2, textAlign: 'right' }} />
    </Paper>
  )
}
