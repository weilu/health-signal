import { Typography, List, ListItem, ListItemText, Divider, Chip, Stack } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { fetchConfig } from '../config.js'
import { useResource } from '../useResource.js'
import { ResourceBoundary } from '../ResourceBoundary.jsx'

export default function ConfigView() {
  const { t, i18n } = useTranslation()
  const state = useResource(fetchConfig)
  return (
    <ResourceBoundary state={state}>
      {(cfg) => (
        <>
          <Typography variant="h4" component="h1" gutterBottom>{t('config.title')}</Typography>
          <Typography variant="subtitle2">{t('config.locales')}</Typography>
          <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
            {(cfg.locales || []).map((l) => (
              <Chip
                key={l}
                label={l}
                size="small"
                color={i18n.resolvedLanguage === l ? 'primary' : 'default'}
                variant={i18n.resolvedLanguage === l ? 'filled' : 'outlined'}
              />
            ))}
          </Stack>
          <Divider sx={{ my: 2 }} />
          <Typography variant="subtitle2">{t('config.targets')}</Typography>
          <List dense>
            {(cfg.targets || []).map((target) => (
              <ListItem key={target.id} alignItems="flex-start">
                <ListItemText
                  primary={target.label_key || target.id}
                  secondary={(target.pages || []).map((p) => p.path).join(', ') || '—'}
                />
              </ListItem>
            ))}
          </List>
        </>
      )}
    </ResourceBoundary>
  )
}
