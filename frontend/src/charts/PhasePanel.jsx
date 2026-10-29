import { useCallback, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Alert, Box, Button, Paper, Stack, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { fetchData, fetchPhases, fetchPhaseStreams } from '../api.js'
import { activeWeeks, phaseRuns, phaseSince, pickInRange } from '../assessments.js'
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
function StreamChart({ stream, range, shading, axisWidth, onAxisWidth, named }) {
  const { t } = useTranslation()
  // The stream's own location, as the producer recorded it: without a location filter, the feed may hold others.
  const params = { feed: stream.feed, ...stream.series, location: stream.location, week_from: range?.from, week_to: range?.to }
  const query = useQuery({ queryKey: ['data', params], queryFn: () => fetchData(params) })
  const role = t(`role.${stream.role}`, { defaultValue: stream.role })
  // Without a location filter streams of several regions can sit together; the heading says whose this is.
  const label = named ? `${role} · ${stream.location}` : role
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
            : <TimeSeriesChart periods={model.periods} series={series} unit={unit} shading={shading} height={180}
                axisWidth={axisWidth} onAxisWidth={onAxisWidth} />
        }}
      </ResourceBoundary>
    </Box>
  )
}

function phaseLabel(t, row, rows, method) {
  if (method.active_phases.includes(row.phase)) {
    return t('phase.since', { phase: t(`phase.${row.phase}`), week: weekStamp(t, phaseSince(rows, row.period, method.active_phases)) })
  }
  return t(`phase.${row.phase}`)
}

export function PhasePanel({ panel, target, location, range, latest }) {
  const { t } = useTranslation()
  const method = useMethod()
  const base = phaseQuery(target, location, method)
  const phases = useQuery({ queryKey: ['phases', base], queryFn: () => fetchPhases(base), enabled: !!method })
  const streams = useQuery({ queryKey: ['phase-streams', base], queryFn: () => fetchPhaseStreams(base), enabled: !!method })
  const title = configLabel(t, panel.label_key, panel.id)
  const [axisWidth, setAxisWidth] = useState(0)
  // Only ever grows, so the charts settle after one pass instead of re-fitting each other.
  const reportAxis = useCallback((width) => setAxisWidth((widest) => Math.max(widest, Math.ceil(width))), [])
  const rows = phases.data ?? []
  // A declared phase can stand without observation feeds, so no dashboard range: its own weeks bound it then.
  const span = range ?? (rows.length ? { from: rows.reduce((m, r) => (r.period < m ? r.period : m), rows[0].period),
                                          to: rows.reduce((m, r) => (r.period > m ? r.period : m), rows[0].period) } : null)
  const pick = rows.length && span ? pickInRange(rows, span, latest ?? span.to) : null
  // The rule in the terms of the pathogen's own pattern: seasons or year-round waves, read off its phase codes.
  const pattern = rows.some((r) => r.phase === 'in_wave' || r.phase === 'between_waves') ? 'waves' : 'season'
  const rule = method && t(`methods.${method.name}.phase_rule.${pattern}`, { defaultValue: '' })
  // Without a location filter, several locations' phases can share a week; none of them is "the" phase.
  const tile = pick && (pick.ambiguous ? (
    <Tile title={t(`phase.title.${pattern}`)} current>
      <Typography variant="body1" component="p">{t('phase.ambiguous')}</Typography>
    </Tile>
  ) : pick.row ? (
    <Tile title={t(`phase.title.${pattern}`)} current={pick.current} footer={asOfFooter(t, pick, pick.row.method, `phase.${pattern}`)} note={rule}>
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
                    <StreamChart key={`${s.location}/${s.role}`} stream={s} range={range} axisWidth={axisWidth} named={!location}
                      onAxisWidth={reportAxis}
                      shading={activeWeeks(loaded.filter((r) => r.location === s.location), method.active_phases)} />
                  ))}
                </Stack>
              )}
            </ResourceBoundary>
          )
        }}
      </ResourceBoundary>
    </Paper>
  )
  const runs = pick?.row ? phaseRuns(rows, span, method.active_phases) : null
  const runsTitle = t(`phase.runs.${pattern}`)
  // The shaded bands as text: their weeks, readable without the charts (and by screen readers).
  const runsTile = runs && (
    <Paper component="section" variant="outlined" aria-label={runsTitle} sx={{ px: 3, py: 2.75 }}>
      <Typography variant="overline" color="text.secondary" component="p">{runsTitle}</Typography>
      {runs.length ? (
        <Box component="ul" sx={{ m: 0, p: 0, listStyle: 'none' }}>
          {runs.map((r) => (
            <Typography key={r.from} component="li" variant="body2" sx={{ py: 0.25 }}>
              {[`${weekStamp(t, r.from)} – ${r.ongoing ? t('phase.ongoing') : weekStamp(t, r.to)}`,
                t('phase.weeks', { count: r.weeks }),
                r.startsBefore && t('phase.startedBefore'),
                r.endsAfter && !r.ongoing && t('phase.endsAfter')].filter(Boolean).join(' · ')}
            </Typography>
          ))}
        </Box>
      ) : <Typography variant="body2" color="text.secondary">{t(`phase.noRuns.${pattern}`)}</Typography>}
    </Paper>
  )
  return <TileGrid card={card} tiles={tile && <Stack spacing={2.25}>{tile}{runsTile}</Stack>} />
}
