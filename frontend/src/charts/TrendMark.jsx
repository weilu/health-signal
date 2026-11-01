import { Box, SvgIcon } from '@mui/material'
import { toneColor, trendTone } from '../assessments.js'

// Material's arrow_upward / arrow_forward / arrow_downward.
const ARROWS = {
  increasing: ['up', 'M4 12l1.41 1.41L11 7.83V20h2V7.83l5.58 5.59L20 12l-8-8-8 8z'],
  stable: ['flat', 'M12 4l-1.41 1.41L16.17 11H4v2h12.17l-5.58 5.59L12 20l8-8z'],
  decreasing: ['down', 'M20 12l-1.41-1.41L13 16.17V4h-2v12.17l-5.58-5.59L4 12l8 8 8-8z'],
}

// Beside the trend's word, so hidden from screen readers. The shape carries the direction (it reads without
// colour); no direction is a grey dot, as an ungraded level is, never a flat arrow that would read as stable.
export function TrendMark({ trend, size = 16 }) {
  const arrow = ARROWS[trend]
  if (!arrow) {
    const dot = Math.round(size * 0.65)
    return <Box data-mark="none" aria-hidden sx={{ width: size, height: size, flexShrink: 0, display: 'grid', placeItems: 'center' }}>
      <Box sx={{ width: dot, height: dot, borderRadius: '50%', bgcolor: toneColor('neutral') }} />
    </Box>
  }
  const [mark, path] = arrow
  return (
    <SvgIcon data-mark={mark} aria-hidden sx={{ fontSize: size, flexShrink: 0, color: toneColor(trendTone(trend)) }}>
      <path d={path} />
    </SvgIcon>
  )
}
