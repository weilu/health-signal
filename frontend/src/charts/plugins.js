import { endLabelsFit } from '../series.js'

// Behind the line: the method's level bands within each span's weeks, clipped to the axis so a high
// threshold can't rescale it.
export const thresholdBands = {
  id: 'thresholdBands',
  beforeDatasetsDraw(chart, _args, opts) {
    if (!opts.bands?.length) return
    const { ctx, chartArea: area, scales: { x, y }, data: { labels } } = chart
    ctx.save()
    for (const b of opts.bands) {
      const i0 = labels.findIndex((p) => p >= b.from)
      const i1 = labels.findLastIndex((p) => p <= b.to)
      if (i0 < 0 || i1 < i0) continue
      const top = Math.max(area.top, y.getPixelForValue(Math.min(b.upper, y.max)))
      const bottom = Math.min(area.bottom, y.getPixelForValue(Math.max(b.lower, y.min)))
      if (bottom <= top) continue
      const left = x.getPixelForValue(i0)
      const width = x.getPixelForValue(i1) - left
      ctx.fillStyle = opts.colour(b.level)
      ctx.fillRect(left, top, width, bottom - top)
      // A dashed boundary at each threshold, and the level named inside its band: direct labels, no key.
      if (Number.isFinite(b.lower) && b.lower >= y.min && b.lower <= y.max) {
        ctx.strokeStyle = opts.lineColour
        ctx.setLineDash([4, 3])
        ctx.beginPath()
        ctx.moveTo(left, bottom)
        ctx.lineTo(left + width, bottom)
        ctx.stroke()
        ctx.setLineDash([])
      }
      if (bottom - top >= 14) {
        ctx.fillStyle = opts.labelColour
        ctx.font = opts.font
        ctx.textBaseline = 'middle'
        ctx.fillText(opts.labelFor(b.level), left + 6, (top + bottom) / 2)
      }
    }
    ctx.restore()
  },
}

// Shades the weeks a series (or pathogen) is in season or in a wave.
export const phaseShading = {
  id: 'phaseShading',
  beforeDatasetsDraw(chart, _args, opts) {
    if (!opts.weeks?.size) return
    const { ctx, chartArea: area, scales: { x }, data: { labels } } = chart
    const half = labels.length > 1 ? (x.getPixelForValue(1) - x.getPixelForValue(0)) / 2 : 4
    ctx.save()
    ctx.fillStyle = opts.colour
    labels.forEach((p, i) => {
      if (opts.weeks.has(p)) ctx.fillRect(x.getPixelForValue(i) - half, area.top, half * 2, area.bottom - area.top)
    })
    ctx.restore()
  },
}

// Hairline at the hovered week: readers aim at a date, not a 2px line.
export const crosshair = {
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

const LABEL_GAP = 14  // px between end-label baselines at 12px type

// Ink, never the series colour; only series reaching the last week; none if any would collide.
export const endLabels = {
  id: 'endLabels',
  afterDatasetsDraw(chart, _args, opts) {
    if (!opts.enabled) return
    const last = chart.data.labels.length - 1
    const ends = chart.data.datasets
      .map((ds, i) => ({ label: ds.label, point: chart.getDatasetMeta(i).data[last], visible: chart.isDatasetVisible(i) && ds.data[last] != null }))
      .filter((e) => e.visible && e.point)
    if (!endLabelsFit(ends.map((e) => e.point.y), LABEL_GAP)) return
    const { ctx } = chart
    ctx.save()
    ctx.fillStyle = opts.color
    ctx.font = opts.font
    ctx.textBaseline = 'middle'
    ends.forEach((e) => ctx.fillText(e.label, e.point.x + 6, e.point.y))
    ctx.restore()
  },
}
