import { Stack, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { PhasePanel } from '../charts/PhasePanel.jsx'
import { SummaryPanel } from '../charts/SummaryPanel.jsx'
import { TimeSeriesPanel } from '../charts/TimeSeriesPanel.jsx'
import { groupPanels } from '../groups.js'

const PANELS = { timeseries: TimeSeriesPanel, phase: PhasePanel, summary: SummaryPanel }

// The shell's tabs name the target and page, so this renders only the panels, nested under the same groups the
// overview's summary uses where the page has more than one.
export default function TargetPage({ target, page, location, range, latest }) {
  const { t } = useTranslation()
  if (!page.panels.length) return <Typography color="text.secondary">{t('page.noPanels')}</Typography>
  return (
    <Stack spacing={5}>
      {groupPanels(t, page.panels).map(({ key, heading, items }) => (
        <Stack key={key} component="section" spacing={3} aria-label={heading && [heading.source, heading.kind].filter(Boolean).join(' · ')}>
          {heading && (
            <Stack direction={{ xs: 'column', md: 'row' }} sx={{ columnGap: 1.5, alignItems: { md: 'baseline' } }}>
              <Typography variant="h5" component="h2">{[heading.source, heading.kind].filter(Boolean).join(' · ')}</Typography>
              {heading.shared && <Typography variant="body2" color="text.secondary">{heading.shared}</Typography>}
            </Stack>
          )}
          {items.map((panel) => {
            const Panel = PANELS[panel.type]
            return <Panel key={panel.id} panel={panel} target={target} location={location} range={range} latest={latest} />
          })}
        </Stack>
      ))}
    </Stack>
  )
}
