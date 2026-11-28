import { useMemo } from 'react'
import { Box } from '@mui/material'
import { alpha, useTheme } from '@mui/material/styles'
import { useTranslation } from 'react-i18next'
import { CategoryScale, Chart as ChartJS, Legend, LinearScale, LineElement, LogarithmicScale, PointElement, Tooltip } from 'chart.js'
import { Line } from 'react-chartjs-2'
import { bandAlpha, levelTone, tonePaint } from '../assessments.js'
import { axisNumber, weekStamp } from '../labels.js'
import { dotRadius, isolated } from '../series.js'
import { useAlignedAxis } from './AlignedCharts.jsx'
import { crosshair, endLabels, floorMarkers, phaseShading, thresholdBands } from './plugins.js'

ChartJS.register(CategoryScale, LinearScale, LogarithmicScale, LineElement, PointElement, Tooltip, Legend)

function oneTwoFive(value) {
  const mantissa = value / 10 ** Math.floor(Math.log10(value) + 1e-9)
  return [1, 2, 5].some((m) => Math.abs(mantissa - m) < 1e-6)
}

export function useChartPalette() {
  const theme = useTheme()
  return theme.palette.chart?.[theme.palette.mode] ?? []
}

// `levels` are the method's ordered levels: the chart colours and names its bands from them, as the tiles do.
// Before layout there's no drawn width yet: room enough.
const weekSpacing = (chart) => (chart?.chartArea ? chart.chartArea.width / Math.max(chart.data.labels.length - 1, 1) : Infinity)

// `hidden`: keys of lines a reader turned off, with SeriesToggles as the legend in place of the canvas's.
export function TimeSeriesChart({ periods, series, unit, bands = [], levels = [], shading = null, scale = 'linear', height = 320,
                                 hidden = null }) {
  const { axisWidth, onAxisWidth } = useAlignedAxis()
  const theme = useTheme()
  const { t, i18n } = useTranslation()
  const palette = useChartPalette()
  const fmt = new Intl.NumberFormat(i18n.resolvedLanguage, { maximumFractionDigits: 2 })
  const tick = axisNumber(i18n.resolvedLanguage)
  const { primary: ink, secondary: ink2 } = theme.palette.text
  const rule = theme.palette.divider
  const font = { family: theme.typography.fontFamily, size: 12 }
  const visible = hidden ? series.filter((s) => !hidden.has(s.key)) : series
  const labelled = visible.length >= 2 && visible.length <= 4
  const labelFont = `12px ${theme.typography.fontFamily}`
  // Room for the longest end-label so it isn't clipped.
  const labelRoom = useMemo(() => {
    if (!labelled) return 8
    const ctx = document.createElement('canvas').getContext('2d')
    ctx.font = labelFont
    return Math.ceil(Math.max(...visible.map((s) => ctx.measureText(s.label).width))) + 12
  }, [labelled, labelFont, visible])
  const log = scale === 'log'
  // A zero (e.g. a non-detect's stand-in) has no place on a log axis: a gap in the line, marked at the floor.
  const floor = log ? series.flatMap((s, i) => s.values.flatMap((v, j) => (v != null && v <= 0 ? [[i, j]] : []))) : []
  // One line has nothing to tell apart, so it's drawn in ink like the text, with a dot at each reported week sized
  // to the room it gets; several take the palette, dotted only where a week stands alone (always, at full size).
  const single = series.length === 1
  const colours = single ? [ink] : palette
  const data = {
    labels: periods,
    datasets: series.map((s, i) => ({
      label: s.label, data: log ? s.values.map((v) => (v > 0 ? v : null)) : s.values, qualities: s.qualities,
      hidden: !!hidden?.has(s.key),
      borderColor: colours[i], backgroundColor: colours[i], pointBackgroundColor: colours[i], pointBorderColor: colours[i],
      borderWidth: single ? 1.8 : 2, borderCapStyle: 'round', borderJoinStyle: 'round',
      pointRadius: (c) => (isolated(c.dataset.data, c.dataIndex) ? 3 : single ? dotRadius(weekSpacing(c.chart)) : 0),
      pointHoverRadius: 4, pointHoverBorderWidth: 2, pointHoverBorderColor: theme.palette.background.paper,
    })),
  }
  // An ungraded level has no tone of its own; grey keeps it from reading as "all clear".
  const bandColour = (level) => alpha(tonePaint(theme, levelTone(levels, level)), bandAlpha(levels, level))
  const options = {
    responsive: true, maintainAspectRatio: false, animation: false,
    interaction: { mode: 'index', intersect: false },
    layout: { padding: { right: labelRoom } },
    scales: {
      // Room between week labels, so a narrow chart skips some rather than running them together.
      x: { grid: { display: false }, border: { color: rule }, ticks: { color: ink2, font, maxTicksLimit: 10, maxRotation: 0, autoSkipPadding: 16,
                                                                     callback(value) { return weekStamp(t, this.getLabelForValue(value)) } } },
      y: {
        type: log ? 'logarithmic' : 'linear',
        // On its own line: a long unit plus "log scale" would clip.
        title: { display: true, text: log ? [unit, t('chart.logScale')] : unit, color: ink2, font },
        // Grid lines and labels at 1, 2 and 5 of each decade on a log axis: some even within one decade, without
        // crowding several; Chart.js's other minor ticks would only clutter it.
        grid: { color: (c) => (!log || oneTwoFive(c.tick.value) ? rule : 'transparent'), lineWidth: 1 },
        border: { display: false },
        ticks: { color: ink2, font, callback: (v) => (!log || oneTwoFive(v) ? tick(v) : '') },
        // Stacked charts share the widest y-axis, so their plots start at the same x and weeks line up.
        afterFit: (scale) => {
          onAxisWidth(scale.width)
          scale.width = Math.max(scale.width, axisWidth)
        },
      },
    },
    plugins: {
      // Identifies series only: click-to-hide isn't keyboard-operable on a canvas.
      legend: { display: series.length >= 2 && !hidden, onClick: null, align: 'start', labels: { color: ink, font, usePointStyle: true, pointStyle: 'line' } },
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
      floorMarkers: { points: floor, colours },
    },
  }
  return (
    <Box sx={{ height }}>
      <Line data={data} options={options} plugins={[phaseShading, thresholdBands, crosshair, endLabels, floorMarkers]} />
    </Box>
  )
}
