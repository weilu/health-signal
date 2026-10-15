import { NavLink } from 'react-router-dom'
import { Stack, Tab, Tabs, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { TimeSeriesPanel } from '../charts/TimeSeriesPanel.jsx'
import { configLabel } from '../labels.js'

export default function TargetPage({ target, page }) {
  const { t } = useTranslation()
  return (
    <>
      <Typography variant="h4" component="h1" gutterBottom>{configLabel(t, target.label_key, target.id)}</Typography>
      {target.pages.length > 1 && (
        <Tabs value={page.path} sx={{ mb: 2 }}>
          {target.pages.map((p) => (
            <Tab key={p.path} value={p.path} component={NavLink} to={p.path} end label={configLabel(t, p.label_key, p.id)} />
          ))}
        </Tabs>
      )}
      {page.panels.length === 0
        ? <Typography color="text.secondary">{t('page.noPanels')}</Typography>
        : <Stack spacing={3}>{page.panels.map((panel) => <TimeSeriesPanel key={panel.id} panel={panel} />)}</Stack>}
    </>
  )
}
