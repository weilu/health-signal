import { useQuery } from '@tanstack/react-query'
import { Alert, Box, Paper, Stack, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { fetchData, fetchPhases, fetchPhaseStreams } from '../api.js'
import { activeWeeks, phaseSince, pickInRange } from '../assessments.js'
import { configLabel, weekStamp } from '../labels.js'
import { ResourceBoundary } from '../ResourceBoundary.jsx'
import { toChartModel } from '../series.js'
import { useMethod } from '../useMethod.js'
import { NoneInRange, Tile, asOfFooter } from './StatusTrendTiles.jsx'
import { TimeSeriesChart } from './TimeSeriesChart.jsx'

export function phaseQuery(target, location, method) {
  return { pathogen: target.id, location: location?.value, method: method?.name }
}

// One compact chart per stream on the same weeks: the streams' units differ, so they can't share an axis.
function StreamChart({ stream, location, range, shading }) {
  const { t } = useTranslation()
  const params = { feed: stream.feed, ...stream.series, location: location?.value, week_from: range?.from, week_to: range?.to }
  const query = useQuery({ queryKey: ['data', params], queryFn: () => fetchData(params) })
  const label = t(`role.${stream.role}`, { defaultValue: stream.role })
  return (
    <Box>
      <Typography variant="subtitle2" component="h3">{label}</Typography>
      <ResourceBoundary query={query}>
        {(rows) => {
          const model = toChartModel(rows, null, 1, range)
          if (model.status !== 'ok') return <Alert severity="info">{t('chart.empty')}</Alert>
          const unit = t(`unit.${model.unit}`, { defaultValue: model.unit })
          return <TimeSeriesChart periods={model.periods} series={[{ ...model.series[0], label }]} unit={unit} shading={shading} height={180} />
        }}
      </ResourceBoundary>
    </Box>
  )
}

function phaseLabel(t, row, rows, method) {
  if (method.active_phases.includes(row.phase)) {
    return t('phase.since', { phase: t(`phase.${row.phase}`), week: weekStamp(t, phaseSince(rows, row.period, method.active_phases)) })
  }
  // A year-round pathogen's quiet weeks read as between waves, not out of season.
  const waves = row.phase === 'out_of_season' && rows.some((r) => r.phase === 'in_wave')
  return t(waves ? 'phase.between_waves' : `phase.${row.phase}`)
}

export function PhasePanel({ panel, target, location, range, latest }) {
  const { t } = useTranslation()
  const method = useMethod()
  const base = phaseQuery(target, location, method)
  const phases = useQuery({ queryKey: ['phases', base], queryFn: () => fetchPhases(base), enabled: !!method })
  const streams = useQuery({ queryKey: ['phase-streams', base], queryFn: () => fetchPhaseStreams(base), enabled: !!method })
  const title = configLabel(t, panel.label_key, panel.id)
  return (
    <Paper component="section" variant="outlined" aria-label={title} sx={{ p: 2 }}>
      <Typography variant="h6" component="h2" sx={{ mb: 1 }}>{title}</Typography>
      <ResourceBoundary query={phases}>
        {(rows) => {
          if (!rows.length) return <Typography color="text.secondary">{t('phase.none')}</Typography>
          const pick = range ? pickInRange(rows, range, latest) : null
          const shading = activeWeeks(rows, method.active_phases)
          return (
            <Stack direction={{ xs: 'column-reverse', md: 'row' }} spacing={2}>
              <Stack spacing={2} sx={{ flex: 1, minWidth: 0 }}>
                {(streams.data ?? []).map((s) => (
                  <StreamChart key={s.role} stream={s} location={location} range={range} shading={shading} />
                ))}
              </Stack>
              {pick && (
                <Box sx={{ width: { md: 240 }, flexShrink: 0 }}>
                  {pick.row ? (
                    <Tile title={t('phase.title')} current={pick.current} footer={asOfFooter(t, pick, pick.row.method)}>
                      <Typography variant="h6" component="p">{phaseLabel(t, pick.row, rows, method)}</Typography>
                    </Tile>
                  ) : <NoneInRange />}
                </Box>
              )}
            </Stack>
          )
        }}
      </ResourceBoundary>
      {method && (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          {t(`methods.${method.name}.phase_rule`, { defaultValue: '' })}
        </Typography>
      )}
    </Paper>
  )
}
