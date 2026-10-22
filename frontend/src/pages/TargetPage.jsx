import { Stack, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { TimeSeriesPanel } from '../charts/TimeSeriesPanel.jsx'

// The shell's tabs name the target and page, so this renders only the panels.
export default function TargetPage({ target, page, location, range, latest }) {
  const { t } = useTranslation()
  if (!page.panels.length) return <Typography color="text.secondary">{t('page.noPanels')}</Typography>
  return <Stack spacing={3}>{page.panels.map((panel) => <TimeSeriesPanel key={panel.id} panel={panel} location={location} range={range} latest={latest} />)}</Stack>
}
