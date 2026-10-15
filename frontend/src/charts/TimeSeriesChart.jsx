import { Box } from '@mui/material'
import { useTheme } from '@mui/material/styles'
import { useTranslation } from 'react-i18next'
import { CategoryScale, Chart as ChartJS, Legend, LinearScale, LineElement, PointElement, Tooltip } from 'chart.js'
import { Line } from 'react-chartjs-2'

ChartJS.register(CategoryScale, LinearScale, LineElement, PointElement, Tooltip, Legend)

// Vertical hairline at the hovered week: readers aim at a date, not at a 2px line.
const crosshair = {
  id: 'crosshair',
  afterDraw(chart, _args, opts) {
    const [active] = chart.tooltip?.getActiveElements() ?? []
    if (!active) return
    const { ctx, chartArea: { top, bottom } } = chart
    ctx.save()
    ctx.strokeStyle = opts.color
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.moveTo(active.element.x, top)
    ctx.lineTo(active.element.x, bottom)
    ctx.stroke()
    ctx.restore()
  },
}

// End-of-line labels (≤4 series) in ink, never the series colour: they back up the legend.
const endLabels = {
  id: 'endLabels',
  afterDatasetsDraw(chart, _args, opts) {
    if (!opts.enabled) return
    const { ctx } = chart
    ctx.save()
    ctx.fillStyle = opts.color
    ctx.font = opts.font
    ctx.textBaseline = 'middle'
    chart.data.datasets.forEach((ds, i) => {
      const point = chart.getDatasetMeta(i).data[ds.data.findLastIndex((v) => v != null)]
      if (point) ctx.fillText(ds.label, point.x + 6, point.y)
    })
    ctx.restore()
  },
}

export function useChartPalette() {
  const theme = useTheme()
  return theme.palette.chart?.[theme.palette.mode] ?? []
}

export function TimeSeriesChart({ periods, series, unit }) {
  const theme = useTheme()
  const { i18n } = useTranslation()
  const palette = useChartPalette()
  const fmt = new Intl.NumberFormat(i18n.resolvedLanguage, { maximumFractionDigits: 2 })
  const { primary: ink, secondary: ink2 } = theme.palette.text
  const rule = theme.palette.divider
  const font = { family: theme.typography.fontFamily, size: 12 }
  const labelled = series.length >= 2 && series.length <= 4
  const data = {
    labels: periods,
    datasets: series.map((s, i) => ({
      label: s.label, data: s.values, borderColor: palette[i], backgroundColor: palette[i],
      borderWidth: 2, borderCapStyle: 'round', borderJoinStyle: 'round', pointRadius: 0,
      pointHoverRadius: 4, pointHoverBorderWidth: 2, pointHoverBorderColor: theme.palette.background.paper,
    })),
  }
  const options = {
    responsive: true, maintainAspectRatio: false, animation: false,
    interaction: { mode: 'index', intersect: false },
    layout: { padding: { right: labelled ? 96 : 8 } },
    scales: {
      x: { grid: { display: false }, border: { color: rule }, ticks: { color: ink2, font, maxTicksLimit: 10, maxRotation: 0 } },
      y: {
        title: { display: true, text: unit, color: ink2, font },
        grid: { color: rule, lineWidth: 1 }, border: { display: false },
        ticks: { color: ink2, font, callback: (v) => fmt.format(v) },
      },
    },
    plugins: {
      legend: { display: series.length >= 2, align: 'start', labels: { color: ink, font, usePointStyle: true, pointStyle: 'line' } },
      tooltip: {
        usePointStyle: true, backgroundColor: theme.palette.background.paper, titleColor: ink, bodyColor: ink,
        borderColor: rule, borderWidth: 1, titleFont: font, bodyFont: font,
        callbacks: {
          label: (c) => (c.parsed.y == null ? null : `${fmt.format(c.parsed.y)}  ${c.dataset.label}`),  // value leads
          labelPointStyle: () => ({ pointStyle: 'line', rotation: 0 }),
        },
      },
      crosshair: { color: rule },
      endLabels: { enabled: labelled, color: ink2, font: `12px ${theme.typography.fontFamily}` },
    },
  }
  return (
    <Box sx={{ height: 320 }}>
      <Line data={data} options={options} plugins={[crosshair, endLabels]} />
    </Box>
  )
}
