import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Alert, Box, Button, Chip, Paper, Stack, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { fetchData, fetchPhases, fetchPhaseStreams, fetchThresholds } from '../api.js'
import { activeWeeks, bandsFor, phaseRuns, phaseSince, pickInRange, streamPanel, streamScale } from '../assessments.js'
import { chartTitle, inSentence, panelLabel, weekStamp } from '../labels.js'
import { ResourceBoundary } from '../ResourceBoundary.jsx'
import { toChartModel } from '../series.js'
import { useMethod } from '../useMethod.js'
import { AlignedCharts } from './AlignedCharts.jsx'
import { SeriesTable } from './SeriesTable.jsx'
import { NoneInRange, Tile, TileGrid, asOfFooter } from './StatusTrendTiles.jsx'
import { TimeSeriesChart } from './TimeSeriesChart.jsx'

export function phaseQuery(target, location, method) {
  return { pathogen: target.id, location: location?.value, method: method?.name }
}

// One compact chart per stream on the same weeks: the streams' units differ, so they can't share an axis.
function StreamChart({ stream, range, shading, named, scale, method, name: panelName }) {
  const { t } = useTranslation()
  // The stream's own location, as the producer recorded it: without a location filter, the feed may hold others.
  const params = { feed: stream.feed, ...stream.series, location: stream.location, week_from: range?.from, week_to: range?.to }
  const query = useQuery({ queryKey: ['data', params], queryFn: () => fetchData(params) })
  // Its levels, as its own tab shades them; without them the chart still stands.
  const tParams = { ...params, method: method.name }
  const thresholds = useQuery({ queryKey: ['thresholds', tParams], queryFn: () => fetchThresholds(tParams) })
  const bands = bandsFor((thresholds.data ?? []).filter((r) => r.location === stream.location), method.levels)
  // What it stands for, then what measures it, named as on its tab (or by its indicator, with no panel there).
  const name = panelName ?? t(`indicators.${stream.series.indicator}`, { defaultValue: stream.series.indicator })
  const title = t('phase.streamTitle', { role: t(`role.${stream.role}`, { defaultValue: stream.role }),
                                         indicator: inSentence(name) })
  // Without a location filter streams of several regions can sit together; the heading says whose this is.
  const heading = named ? `${title} (${stream.location})` : title
  const [asTable, setAsTable] = useState(false)
  return (
    <Box>
      <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="subtitle2" component="h3">{heading}</Typography>
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
          const series = [{ ...model.series[0], label: name }]
          return asTable
            ? <SeriesTable periods={model.periods} series={series} unit={unit} />
            : <TimeSeriesChart periods={model.periods} series={series} unit={unit} shading={shading} scale={scale}
                bands={bands} levels={method.levels} height={180} />
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
  const rows = phases.data ?? []
  // A declared phase can stand without observation feeds, so no dashboard range: its own weeks bound it then.
  const span = range ?? (rows.length ? { from: rows.reduce((m, r) => (r.period < m ? r.period : m), rows[0].period),
                                          to: rows.reduce((m, r) => (r.period > m ? r.period : m), rows[0].period) } : null)
  const pick = rows.length && span ? pickInRange(rows, span, latest ?? span.to) : null
  // The rule in the terms of the pathogen's own pattern: seasons or year-round waves, read off its phase codes, or
  // the config's before there are any.
  const pattern = rows.length ? (rows.some((r) => r.phase === 'in_wave' || r.phase === 'between_waves') ? 'waves' : 'season')
    : panel.pattern ?? 'season'
  const title = chartTitle(t, panel, target, location)
  const rule = method && t(`methods.${method.name}.phase_rule.${pattern}`, { defaultValue: '' })
  // Streams with no phase yet (one not graded): their charts still say something, the tile says why there's no phase.
  const undetermined = phases.data && !rows.length && streams.data?.length
  // Without a location filter, several locations' phases can share a week; none of them is "the" phase.
  const tile = undetermined ? (
    <Tile title={t(`phase.title.${pattern}`)} current note={t('phase.undeterminedNote')}>
      <Typography variant="h5" component="p">{t(`phase.undetermined.${pattern}`)}</Typography>
    </Tile>
  ) : pick && (pick.ambiguous ? (
    <Tile title={t(`phase.title.${pattern}`)} current>
      <Typography variant="body1" component="p">{t('phase.ambiguous')}</Typography>
    </Tile>
  ) : pick.row ? (
    <Tile title={t(`phase.title.${pattern}`)} current={pick.current} footer={asOfFooter(t, pick, pick.row.method, `phase.${pattern}`)} note={rule}>
      <Stack direction="row" spacing={1.25} sx={{ alignItems: 'center' }}>
        <Typography variant="h5" component="p">{phaseLabel(t, pick.row, rows, method)}</Typography>
        {pick.row.provisional && <Chip size="small" variant="outlined" label={t('assessment.provisional')} />}
      </Stack>
    </Tile>
  ) : <NoneInRange />)
  const card = (
    <Paper component="section" variant="outlined" aria-label={title} sx={{ p: 2, minWidth: 0 }}>
      <Typography variant="h6" component="h2" sx={{ mb: 1 }}>{title}</Typography>
      <ResourceBoundary query={phases}>
        {(loaded) => {
          // A declared or stream-less phase has no evidence to chart; the card keeps just the rule text.
          return (
            <ResourceBoundary query={streams}>
              {(list) => !loaded.length && !list.length ? <Typography color="text.secondary">{t('phase.none')}</Typography> : (
                <AlignedCharts>
                  <Stack spacing={2}>
                    {list.map((s) => (
                      <StreamChart key={`${s.location}/${s.role}`} stream={s} range={range} named={!location} method={method}
                        scale={streamScale(target, s)} name={streamPanel(target, s) && panelLabel(t, streamPanel(target, s))}
                        shading={activeWeeks(loaded.filter((r) => r.location === s.location), method.active_phases)} />
                    ))}
                  </Stack>
                </AlignedCharts>
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
