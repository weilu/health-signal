import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Navigate } from 'react-router-dom'
import { Alert, Button, Paper, Stack, Typography } from '@mui/material'
import { alpha, useTheme } from '@mui/material/styles'
import { useTranslation } from 'react-i18next'
import { fetchAssessments, fetchData, fetchThresholds } from '../api.js'
import { activeWeeks, assessmentParams, bandAlpha, bandsFor, combinedState, levelTone, pickInRange } from '../assessments.js'
import { useMethod } from '../useMethod.js'
import { StatusTrendTiles, TileGrid } from './StatusTrendTiles.jsx'
import { ResourceBoundary } from '../ResourceBoundary.jsx'
import { toChartModel } from '../series.js'
import { configLabel, weekStamp } from '../labels.js'
import { panelParams } from '../filters.js'
import { SeriesTable } from './SeriesTable.jsx'
import { TimeSeriesChart, useChartPalette } from './TimeSeriesChart.jsx'

export function TimeSeriesPanel({ panel, location, range, latest }) {
  const { t } = useTranslation()
  const theme = useTheme()
  const palette = useChartPalette()
  const method = useMethod()
  const [asTable, setAsTable] = useState(false)
  const params = panelParams(panel.query, location?.value, range)
  const query = useQuery({ queryKey: ['data', params], queryFn: () => fetchData(params) })
  // Tiles describe one series, so panels split into several lines get none.
  const single = !panel.series_by && !!method
  const aParams = { ...assessmentParams(params), method: method?.name }
  const assessed = useQuery({ queryKey: ['assessments', aParams], queryFn: () => fetchAssessments(aParams), enabled: single })
  const tParams = { ...params, method: method?.name }
  const thresholds = useQuery({ queryKey: ['thresholds', tParams], queryFn: () => fetchThresholds(tParams), enabled: single })
  const pick = single && range && assessed.data ? pickInRange(assessed.data, range, latest) : null
  // Cached rows keep serving through a failed refetch; only a lookup that never loaded counts as failed.
  const lookups = single ? combinedState([assessed, thresholds]) : 'ok'
  const chartExtras = single ? {
    bands: bandsFor(thresholds.data ?? [], method.levels),
    bandColour: (level) => alpha(theme.palette[levelTone(method.levels, level)].main, bandAlpha(method.levels, level)),
    bandLabel: (level) => t(`level.${level}`),
    shading: activeWeeks(assessed.data ?? [], method.active_phases),
  } : {}
  const title = configLabel(t, panel.label_key, panel.id)
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
          const series = model.series.map((s) => ({ ...s, label: panel.series_by ? s.key || t('chart.unspecified') : title }))
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
    : pick && !pick.ambiguous && <StatusTrendTiles pick={pick} method={method} />
  return <TileGrid card={card} tiles={tiles} />
}
