import { useEffect, useState } from 'react'
import { Typography, List, ListItem, ListItemText, Divider, Chip, Stack, Alert, Button } from '@mui/material'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { fetchConfig } from '../config.js'

export default function ConfigView() {
  const { t } = useTranslation()
  const [state, setState] = useState({ status: 'loading' })

  useEffect(() => {
    let live = true
    fetchConfig()
      .then((cfg) => { if (live) setState({ status: 'ok', cfg }) })
      .catch((e) => { if (live) setState({ status: e.status === 401 ? 'unauth' : 'error' }) })
    return () => { live = false }
  }, [])

  if (state.status === 'loading') return <Typography>{t('app.loading')}</Typography>
  if (state.status === 'unauth') return <Button component={Link} to="/login" variant="contained">{t('login.submit')}</Button>
  if (state.status === 'error') return <Alert severity="error">{t('config.error')}</Alert>

  const { cfg } = state
  return (
    <>
      <Typography variant="h4" gutterBottom>{t('config.title')}</Typography>
      <Typography variant="subtitle2">{t('config.locales')}</Typography>
      <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
        {(cfg.locales || []).map((l) => <Chip key={l} label={l} size="small" />)}
      </Stack>
      <Divider sx={{ my: 2 }} />
      <Typography variant="subtitle2">{t('config.targets')}</Typography>
      <List dense>
        {(cfg.targets || []).map((target) => (
          <ListItem key={target.id} alignItems="flex-start">
            <ListItemText
              primary={target.label_key || target.id}
              secondary={(target.pages || []).map((p) => p.path).join('  ·  ') || '—'}
            />
          </ListItem>
        ))}
      </List>
    </>
  )
}
