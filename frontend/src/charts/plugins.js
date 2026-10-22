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
      ctx.fillStyle = opts.colour(b.level)
      ctx.fillRect(x.getPixelForValue(i0), top, x.getPixelForValue(i1) - x.getPixelForValue(i0), bottom - top)
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
