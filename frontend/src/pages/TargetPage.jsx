import { Stack, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { TimeSeriesPanel } from '../charts/TimeSeriesPanel.jsx'

// The target and page are named by the selected tabs in the shell, so the page renders only its panels.
export default function TargetPage({ page }) {
  const { t } = useTranslation()
  if (!page.panels.length) return <Typography color="text.secondary">{t('page.noPanels')}</Typography>
  return <Stack spacing={3}>{page.panels.map((panel) => <TimeSeriesPanel key={panel.id} panel={panel} />)}</Stack>
}
