import { useMemo } from 'react'
import { Box } from '@mui/material'
import { alpha, useTheme } from '@mui/material/styles'
import { useTranslation } from 'react-i18next'
import { CategoryScale, Chart as ChartJS, Legend, LinearScale, LineElement, PointElement, Tooltip } from 'chart.js'
import { Line } from 'react-chartjs-2'
import { bandAlpha, levelTone } from '../assessments.js'
import { axisNumber, weekStamp } from '../labels.js'
import { isolated } from '../series.js'
import { useAlignedAxis } from './AlignedCharts.jsx'
import { crosshair, endLabels, phaseShading, thresholdBands } from './plugins.js'

ChartJS.register(CategoryScale, LinearScale, LineElement, PointElement, Tooltip, Legend)

export function useChartPalette() {
  const theme = useTheme()
  return theme.palette.chart?.[theme.palette.mode] ?? []
}

// `levels` are the method's ordered levels: the chart colours and names its bands from them, as the tiles do.
export function TimeSeriesChart({ periods, series, unit, bands = [], levels = [], shading = null, height = 320 }) {
  const { axisWidth, onAxisWidth } = useAlignedAxis()
  const theme = useTheme()
  const { t, i18n } = useTranslation()
  const palette = useChartPalette()
  const fmt = new Intl.NumberFormat(i18n.resolvedLanguage, { maximumFractionDigits: 2 })
  const tick = axisNumber(i18n.resolvedLanguage)
  const { primary: ink, secondary: ink2 } = theme.palette.text
  const rule = theme.palette.divider
  const font = { family: theme.typography.fontFamily, size: 12 }
  const labelled = series.length >= 2 && series.length <= 4
  const labelFont = `12px ${theme.typography.fontFamily}`
  // Room for the longest end-label so it isn't clipped.
  const labelRoom = useMemo(() => {
    if (!labelled) return 8
    const ctx = document.createElement('canvas').getContext('2d')
    ctx.font = labelFont
    return Math.ceil(Math.max(...series.map((s) => ctx.measureText(s.label).width))) + 12
  }, [labelled, labelFont, series])
  const data = {
    labels: periods,
    datasets: series.map((s, i) => ({
      label: s.label, data: s.values, qualities: s.qualities, borderColor: palette[i], backgroundColor: palette[i],
      borderWidth: 2, borderCapStyle: 'round', borderJoinStyle: 'round',
      pointRadius: (c) => (isolated(c.dataset.data, c.dataIndex) ? 3 : 0),
      pointHoverRadius: 4, pointHoverBorderWidth: 2, pointHoverBorderColor: theme.palette.background.paper,
    })),
  }
  // An ungraded level has no tone of its own; grey keeps it from reading as "all clear".
  const bandColour = (level) => {
    const tone = levelTone(levels, level)
    return alpha(tone === 'neutral' ? theme.palette.grey[500] : theme.palette[tone].main, bandAlpha(levels, level))
  }
  const options = {
    responsive: true, maintainAspectRatio: false, animation: false,
    interaction: { mode: 'index', intersect: false },
    layout: { padding: { right: labelRoom } },
    scales: {
      // Room between week labels, so a narrow chart skips some rather than running them together.
      // Weeks read as everywhere else in the app (W27 2025, Εβδ. 27/2025), not as ISO codes.
      x: { grid: { display: false }, border: { color: rule }, ticks: { color: ink2, font, maxTicksLimit: 10, maxRotation: 0, autoSkipPadding: 16,
                                                                     callback(value) { return weekStamp(t, this.getLabelForValue(value)) } } },
      y: {
        title: { display: true, text: unit, color: ink2, font },
        grid: { color: rule, lineWidth: 1 }, border: { display: false },
        ticks: { color: ink2, font, callback: (v) => tick(v) },
        // Stacked charts share the widest y-axis, so their plots start at the same x and weeks line up.
        afterFit: (scale) => {
          onAxisWidth(scale.width)
          scale.width = Math.max(scale.width, axisWidth)
        },
      },
    },
    plugins: {
      // Identifies series only: click-to-hide isn't keyboard-operable on a canvas.
      legend: { display: series.length >= 2, onClick: null, align: 'start', labels: { color: ink, font, usePointStyle: true, pointStyle: 'line' } },
      tooltip: {
        usePointStyle: true, backgroundColor: theme.palette.background.paper, titleColor: ink, bodyColor: ink,
        borderColor: rule, borderWidth: 1, titleFont: font, bodyFont: font,
        callbacks: {
          title: (items) => (items.length ? weekStamp(t, items[0].label) : ''),
          label: (c) => {
            if (c.parsed.y == null) return null
            const q = c.dataset.qualities?.[c.dataIndex]
            // A below-detection value is the producer's stand-in (0, LOD/2, …), not a measurement.
            const value = q ? t(`quality.${q}`, { defaultValue: q }) : fmt.format(c.parsed.y)
            return `${value}  ${c.dataset.label}`  // value leads
          },
          labelPointStyle: () => ({ pointStyle: 'line', rotation: 0 }),
        },
      },
      crosshair: { color: rule },
      thresholdBands: { bands, colour: bandColour, labelFor: (level) => t(`level.${level}`), lineColour: alpha(ink2, 0.5), labelColour: ink2, font: `11px ${theme.typography.fontFamily}` },
      phaseShading: { weeks: shading, colour: alpha(theme.palette.text.primary, 0.06) },
      endLabels: { enabled: labelled, color: ink2, font: labelFont },
    },
  }
  return (
    <Box sx={{ height }}>
      <Line data={data} options={options} plugins={[phaseShading, thresholdBands, crosshair, endLabels]} />
    </Box>
  )
}
