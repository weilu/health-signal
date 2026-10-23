import { Stack, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { PhasePanel } from '../charts/PhasePanel.jsx'
import { SummaryPanel } from '../charts/SummaryPanel.jsx'
import { TimeSeriesPanel } from '../charts/TimeSeriesPanel.jsx'

const PANELS = { timeseries: TimeSeriesPanel, phase: PhasePanel, summary: SummaryPanel }

// The shell's tabs name the target and page, so this renders only the panels.
export default function TargetPage({ target, page, location, range, latest }) {
  const { t } = useTranslation()
  if (!page.panels.length) return <Typography color="text.secondary">{t('page.noPanels')}</Typography>
  return (
    <Stack spacing={3}>
      {page.panels.map((panel) => {
        const Panel = PANELS[panel.type]
        return <Panel key={panel.id} panel={panel} target={target} location={location} range={range} latest={latest} />
      })}
    </Stack>
  )
}
