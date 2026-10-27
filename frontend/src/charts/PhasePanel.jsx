import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Alert, Box, Button, Paper, Stack, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { fetchData, fetchPhases, fetchPhaseStreams } from '../api.js'
import { activeWeeks, phaseSince, pickInRange } from '../assessments.js'
import { configLabel, weekStamp } from '../labels.js'
import { ResourceBoundary } from '../ResourceBoundary.jsx'
import { toChartModel } from '../series.js'
import { useMethod } from '../useMethod.js'
import { SeriesTable } from './SeriesTable.jsx'
import { NoneInRange, Tile, TileGrid, asOfFooter } from './StatusTrendTiles.jsx'
import { TimeSeriesChart } from './TimeSeriesChart.jsx'

export function phaseQuery(target, location, method) {
  return { pathogen: target.id, location: location?.value, method: method?.name }
}

// One compact chart per stream on the same weeks: the streams' units differ, so they can't share an axis.
function StreamChart({ stream, range, shading }) {
  const { t } = useTranslation()
  // The stream's own location, as the producer recorded it: without a location filter, the feed may hold others.
  const params = { feed: stream.feed, ...stream.series, location: stream.location, week_from: range?.from, week_to: range?.to }
  const query = useQuery({ queryKey: ['data', params], queryFn: () => fetchData(params) })
  const label = t(`role.${stream.role}`, { defaultValue: stream.role })
  const [asTable, setAsTable] = useState(false)
  return (
    <Box>
      <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="subtitle2" component="h3">{label}</Typography>
        <Button size="small" onClick={() => setAsTable((v) => !v)}>{t(asTable ? 'chart.showChart' : 'chart.showTable')}</Button>
      </Stack>
      <ResourceBoundary query={query}>
        {(rows) => {
          const model = toChartModel(rows, null, 1, range)
          // As the time-series panel does: e.g. mixed units is the producer's to fix, not "no data".
          if (model.status !== 'ok') {
            return <Alert severity={model.status === 'empty' ? 'info' : 'warning'}>{t(`chart.${model.status}`, model)}</Alert>
          }
          const unit = t(`unit.${model.unit}`, { defaultValue: model.unit })
          const series = [{ ...model.series[0], label }]
          return asTable
            ? <SeriesTable periods={model.periods} series={series} unit={unit} />
            : <TimeSeriesChart periods={model.periods} series={series} unit={unit} shading={shading} height={180} />
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
  const rows = phases.data ?? []
  const pick = rows.length && range ? pickInRange(rows, range, latest) : null
  // Without a location filter, several locations' phases can share a week; none of them is "the" phase.
  const tile = pick && (pick.ambiguous ? (
    <Tile title={t('phase.title')} current>
      <Typography variant="body1" component="p">{t('phase.ambiguous')}</Typography>
    </Tile>
  ) : pick.row ? (
    <Tile title={t('phase.title')} current={pick.current} footer={asOfFooter(t, pick, pick.row.method, 'phase')}>
      <Typography variant="h5" component="p">{phaseLabel(t, pick.row, rows, method)}</Typography>
    </Tile>
  ) : <NoneInRange />)
  const card = (
    <Paper component="section" variant="outlined" aria-label={title} sx={{ p: 2, minWidth: 0 }}>
      <Typography variant="h6" component="h2" sx={{ mb: 1 }}>{title}</Typography>
      <ResourceBoundary query={phases}>
        {(loaded) => {
          if (!loaded.length) return <Typography color="text.secondary">{t('phase.none')}</Typography>
          // A declared or stream-less phase has no evidence to chart; the card keeps just the rule text.
          return (
            <ResourceBoundary query={streams}>
              {(list) => (
                <Stack spacing={2}>
                  {list.map((s) => (
                    <StreamChart key={`${s.location}/${s.role}`} stream={s} range={range}
                      shading={activeWeeks(loaded.filter((r) => r.location === s.location), method.active_phases)} />
                  ))}
                </Stack>
              )}
            </ResourceBoundary>
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
  return <TileGrid card={card} tiles={tile} />
}
