import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Alert, Button, Paper, Stack, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { fetchData } from '../api.js'
import { ResourceBoundary } from '../ResourceBoundary.jsx'
import { toChartModel } from '../series.js'
import { configLabel } from '../labels.js'
import { SeriesTable } from './SeriesTable.jsx'
import { TimeSeriesChart, useChartPalette } from './TimeSeriesChart.jsx'

export function TimeSeriesPanel({ panel, location }) {
  const { t } = useTranslation()
  const palette = useChartPalette()
  const [asTable, setAsTable] = useState(false)
  const params = { ...panel.query, location: location?.value }  // the header filter applies to every panel
  const query = useQuery({ queryKey: ['data', params], queryFn: () => fetchData(params) })
  const title = configLabel(t, panel.label_key, panel.id)
  return (
    <Paper component="section" variant="outlined" aria-label={title} sx={{ p: 2 }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
        <Typography variant="h6" component="h2">{title}</Typography>
        <Button size="small" onClick={() => setAsTable((v) => !v)}>{t(asTable ? 'chart.showChart' : 'chart.showTable')}</Button>
      </Stack>
      <ResourceBoundary query={query}>
        {(rows) => {
          const model = toChartModel(rows, panel.series_by, palette.length)
          if (model.status !== 'ok') {
            const message = model.status === 'empty' && location
              ? t('chart.emptyAt', { location: location.label })
              : t(`chart.${model.status}`, model)
            return <Alert severity={model.status === 'empty' ? 'info' : 'warning'}>{message}</Alert>
          }
          const series = model.series.map((s) => ({ ...s, label: panel.series_by ? s.key || t('chart.unspecified') : title }))
          const unit = t(`unit.${model.unit}`, { defaultValue: model.unit })
          return (
            asTable
              ? <SeriesTable periods={model.periods} series={series} unit={unit} />
              : <TimeSeriesChart periods={model.periods} series={series} unit={unit} />
          )
        }}
      </ResourceBoundary>
    </Paper>
  )
}
