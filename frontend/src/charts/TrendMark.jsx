import { Box, SvgIcon } from '@mui/material'
import { alpha } from '@mui/material/styles'
import { toneColor, tonePaint, trendTone } from '../assessments.js'

// Strokes rather than Material's filled arrows, so the weight can be set.
const ARROWS = {
  increasing: ['up', 'M12 17.5V7M7.5 11.5L12 7l4.5 4.5'],
  stable: ['flat', 'M6.5 12H17M12.5 7.5L17 12l-4.5 4.5'],
  decreasing: ['down', 'M12 6.5V17M7.5 12.5L12 17l4.5-4.5'],
}

const HALO = 0.13

// The ring is margin too, so it never overlaps the text beside the dot.
export function ToneDot({ tone, size = 10 }) {
  const ring = Math.max(2, Math.round(size * 0.3))
  return (
    <Box aria-hidden sx={(theme) => ({
      width: size, height: size, m: `${ring}px`, borderRadius: '50%', flexShrink: 0,
      bgcolor: tonePaint(theme, tone), boxShadow: `0 0 0 ${ring}px ${alpha(tonePaint(theme, tone), HALO)}`,
    })} />
  )
}

// Beside the trend's word, so hidden from screen readers. The shape carries the direction (it reads without
// colour); no direction is a grey dot, as an ungraded level is, never a flat arrow that would read as stable.
// The arrow's disc is tinted as a dot's ring is, so status and trend read as one set of marks.
export function TrendMark({ trend, size = 20 }) {
  const arrow = ARROWS[trend]
  if (!arrow) {
    return <Box data-mark="none" aria-hidden sx={{ width: size, height: size, flexShrink: 0, display: 'grid', placeItems: 'center' }}>
      <ToneDot tone="neutral" size={Math.round(size * 0.5)} />
    </Box>
  }
  const [mark, path] = arrow
  return (
    <SvgIcon data-mark={mark} aria-hidden sx={{ fontSize: size, flexShrink: 0, color: toneColor(trendTone(trend)) }}>
      <circle cx="12" cy="12" r="12" fill="currentColor" fillOpacity={HALO} />
      <path d={path} fill="none" stroke="currentColor" strokeWidth="2.75" strokeLinecap="round" strokeLinejoin="round" />
    </SvgIcon>
  )
}
