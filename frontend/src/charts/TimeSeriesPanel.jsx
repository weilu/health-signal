import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Navigate } from 'react-router-dom'
import { Alert, Button, Paper, Stack, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { fetchAssessments, fetchData, fetchThresholds } from '../api.js'
import { activeWeeks, bandsFor, combinedState, ofSeries, pickInRange, plottedSeries, singleSeries } from '../assessments.js'
import { useMethod } from '../useMethod.js'
import { StatusTrendTiles, TileGrid } from './StatusTrendTiles.jsx'
import { ResourceBoundary } from '../ResourceBoundary.jsx'
import { toChartModel } from '../series.js'
import { panelLabel, seriesLabel, weekStamp } from '../labels.js'
import { panelParams } from '../filters.js'
import { SeriesTable } from './SeriesTable.jsx'
import { TimeSeriesChart, useChartPalette } from './TimeSeriesChart.jsx'

export function TimeSeriesPanel({ panel, location, range, latest }) {
  const { t } = useTranslation()
  const palette = useChartPalette()
  const method = useMethod()
  const [asTable, setAsTable] = useState(false)
  const params = panelParams(panel.query, location?.value, range)
  const query = useQuery({ queryKey: ['data', params], queryFn: () => fetchData(params) })
  // Tiles describe one series, so panels split into several lines get none.
  const single = !panel.series_by && !!method
  // Over the whole history, so the range only re-picks a row; the summary builds the same key and shares the cache.
  const aParams = { ...panelParams(panel.query, location?.value), method: method?.name }
  const assessed = useQuery({ queryKey: ['assessments', aParams], queryFn: () => fetchAssessments(aParams), enabled: single })
  const tParams = { ...params, method: method?.name }
  const thresholds = useQuery({ queryKey: ['thresholds', tParams], queryFn: () => fetchThresholds(tParams), enabled: single })
  // Without a location filter the lookups can hold other populations than the one plotted (e.g. Attica's
  // history beside Greece's chart): keep only the plotted series' rows for tiles, bands and shading.
  const plotted = plottedSeries(query.data)
  const own = (rows) => (plotted?.mixed ? [] : plotted ? (rows ?? []).filter((r) => ofSeries(r, plotted)) : rows ?? [])
  const assessedRows = own(assessed.data)
  const thresholdRows = own(thresholds.data)
  const pick = single && range && assessed.data && assessedRows.length ? pickInRange(assessedRows, range, latest) : null
  // Cached rows keep serving through a failed refetch; only a lookup that never loaded counts as failed.
  const lookups = single ? combinedState([assessed, thresholds]) : 'ok'
  // Bands need no assessment history, but neither overlay may merge several series.
  const overlays = single && !pick?.ambiguous && singleSeries([...assessedRows, ...thresholdRows])
  const chartExtras = overlays ? {
    bands: bandsFor(thresholdRows, method.levels),
    levels: method.levels,
    shading: activeWeeks(assessedRows, method.active_phases),
  } : {}
  const title = panelLabel(t, panel)
  const card = (
    <Paper component="section" variant="outlined" aria-label={title} sx={{ p: 2, minWidth: 0 }}>
      <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
        <Typography variant="h6" component="h2">{title}</Typography>
        <Button size="small" onClick={() => setAsTable((v) => !v)}>{t(asTable ? 'chart.showChart' : 'chart.showTable')}</Button>
      </Stack>
      <ResourceBoundary query={query}>
        {(rows) => {
          const model = toChartModel(rows, panel.series_by, palette.length, range)
          if (model.status !== 'ok') {
            const span = range && { from: weekStamp(t, range.from), to: weekStamp(t, range.to) }
            const message = model.status !== 'empty' || !span ? t(`chart.${model.status}`, model)
              : location ? t('chart.emptyAt', { location: location.label, ...span }) : t('chart.emptyIn', span)
            return <Alert severity={model.status === 'empty' ? 'info' : 'warning'}>{message}</Alert>
          }
          const series = model.series.map((s) => ({ ...s, label: panel.series_by ? seriesLabel(t, panel.series_by, s.key) : title }))
          const unit = t(`unit.${model.unit}`, { defaultValue: model.unit })
          return asTable
            ? <SeriesTable periods={model.periods} series={series} unit={unit} />
            : <TimeSeriesChart periods={model.periods} series={series} unit={unit} {...chartExtras} />
        }}
      </ResourceBoundary>
    </Paper>
  )
  if (lookups === 'unauth') return <Navigate to="/login" replace />
  // A failed lookup must not read as "never assessed"; an ambiguous one leaves the chart's own warning to explain.
  const tiles = lookups === 'error' ? <Alert severity="warning">{t('assessment.unavailable')}</Alert>
    : pick?.ambiguous ? <Alert severity="info">{t('assessment.ambiguous')}</Alert>
    : pick && <StatusTrendTiles pick={pick} method={method} />
  return <TileGrid card={card} tiles={tiles} />
}
