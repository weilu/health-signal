import { Box, Chip, Paper, Stack, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { weekStamp } from '../labels.js'
import { levelTone, toneColor, trendTone } from '../assessments.js'
import { ToneDot, TrendMark } from './TrendMark.jsx'

// growth_* are proportional change per period (spec §6.3), so -0.2 reads -20%/wk.
const pct = (v) => `${v > 0 ? '+' : ''}${Math.round(v * 100)}%`

// The chart card and its tiles as sibling cards: the tiles hold a word and a footnote, so a bounded column and the
// chart the rest; below a laptop's width they stack, rather than squeeze the chart.
export function TileGrid({ card, tiles }) {
  if (!tiles) return card
  return (
    <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: 'minmax(0, 1fr) clamp(320px, 28%, 420px)' }, gap: 3, alignItems: 'start' }}>
      {card}
      {tiles}
    </Box>
  )
}

// Not-current tiles are dashed and muted so a past state isn't read as now (spec §9).
export function Tile({ title, current, footer, note, children }) {
  return (
    <Paper component="section" variant="outlined" aria-label={title}
      sx={{ px: 3, py: 2.75, opacity: current ? 1 : 0.75, borderStyle: current ? 'solid' : 'dashed' }}>
      <Typography variant="overline" color="text.secondary" component="p">{title}</Typography>
      {children}
      <Typography variant="caption" color="text.secondary" component="p" sx={{ mt: 1 }}>{footer}</Typography>
      {note && <Typography variant="body2" color="text.secondary" component="p" sx={{ mt: 1.5 }}>{note}</Typography>}
    </Paper>
  )
}

export function NoneInRange() {
  const { t } = useTranslation()
  return (
    <Paper variant="outlined" sx={{ px: 3, py: 2.75 }}>
      <Typography variant="body2" color="text.secondary">{t('assessment.noneInRange')}</Typography>
    </Paper>
  )
}

// Names the part of the method behind the tile (burden levels, growth rate), not just the method: tiles of one
// panel may come from different methods, e.g. MEM's levels beside aedseo's growth rate.
export function asOfFooter(t, pick, method, tile) {
  const source = t(`methods.${method}.sources.${tile}`, { defaultValue: method })
  return t(pick.current ? 'assessment.asOf' : 'assessment.asOfPast', { week: weekStamp(t, pick.asOf), source })
}

// For a tile whose sentence already gives the week: just the source, and whether the week is the latest.
export function sourceFooter(t, pick, method, tile) {
  const source = t(`methods.${method}.sources.${tile}`, { defaultValue: method })
  return t(pick.current ? 'assessment.source' : 'assessment.sourcePast', { source })
}

// The interval alone: it decides the label (stable when it holds 0), so a point estimate would only invite a
// reading the label doesn't make. Worded by the method, whose window it is; the week named only when looking back,
// so the trend tile's footer needs no "as of" (sourceFooter).
export function growthText(t, pick, row) {
  return t(`methods.${row.method}.growth`, { lower: pct(row.growth_lower), upper: pct(row.growth_upper),
                                            week: weekStamp(t, pick.asOf), context: pick.current ? undefined : 'past' })
}

export function StatusTrendTiles({ pick, method }) {
  const { t } = useTranslation()
  if (!pick.row) return <NoneInRange />
  const { row, current } = pick
  const tone = levelTone(method.levels, row.level)
  const trend = trendTone(row.trend)
  return (
    <Stack spacing={2.25}>
      <Tile title={t('assessment.status')} current={current} footer={asOfFooter(t, pick, row.method, 'status')}>
        <Stack direction="row" spacing={1.25} sx={{ alignItems: 'center' }}>
          <ToneDot tone={tone} size={16} />
          <Typography variant="h5" component="p" sx={{ color: tone === 'neutral' ? 'text.secondary' : toneColor(tone) }}>
            {row.level ? t(`level.${row.level}`) : t('assessment.ungraded')}
          </Typography>
          {row.provisional && <Chip size="small" variant="outlined" label={t('assessment.provisional')} />}
        </Stack>
      </Tile>
      <Tile title={t('assessment.trend')} current={current} footer={sourceFooter(t, pick, row.method, 'trend')}>
        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
          {row.trend && <TrendMark trend={row.trend} size={28} />}
          <Typography variant="h5" component="p" sx={{ color: trend === 'neutral' ? 'text.secondary' : toneColor(trend) }}>
            {row.trend ? t(`trend.${row.trend}`) : '—'}
          </Typography>
        </Stack>
        {row.growth_rate != null && (
          <Typography variant="body2" color="text.secondary">
            {growthText(t, pick, row)}
          </Typography>
        )}
      </Tile>
    </Stack>
  )
}
