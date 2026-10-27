import { Box, Chip, Paper, Stack, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { weekStamp } from '../labels.js'
import { levelTone, toneColor } from '../assessments.js'

// growth_* are proportional change per period (spec §6.3), so -0.2 reads -20%/wk.
const pct = (v) => `${v > 0 ? '+' : ''}${Math.round(v * 100)}%`

// The chart card and its tiles as sibling cards, as greece-public-health lays them out; one column on phones.
export function TileGrid({ card, tiles }) {
  if (!tiles) return card
  return (
    <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1.85fr 1fr' }, gap: 3, alignItems: 'start' }}>
      {card}
      {tiles}
    </Box>
  )
}

// Not-current tiles are dashed and muted so a past state isn't read as now (spec §9).
export function Tile({ title, current, footer, children }) {
  return (
    <Paper component="section" variant="outlined" aria-label={title}
      sx={{ px: 3, py: 2.75, opacity: current ? 1 : 0.75, borderStyle: current ? 'solid' : 'dashed' }}>
      <Typography variant="overline" color="text.secondary" component="p">{title}</Typography>
      {children}
      <Typography variant="caption" color="text.secondary" component="p" sx={{ mt: 1 }}>{footer}</Typography>
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

export function StatusTrendTiles({ pick, method }) {
  const { t } = useTranslation()
  if (!pick.row) return <NoneInRange />
  const { row, current } = pick
  const tone = toneColor(levelTone(method.levels, row.level))
  return (
    <Stack spacing={2.25}>
      <Tile title={t('assessment.status')} current={current} footer={asOfFooter(t, pick, row.method, 'status')}>
        <Stack direction="row" spacing={1.25} sx={{ alignItems: 'center' }}>
          <Box sx={{ width: 12, height: 12, borderRadius: '50%', flexShrink: 0, bgcolor: tone }} />
          <Typography variant="h5" component="p" sx={{ color: tone === 'grey.500' ? 'text.secondary' : tone }}>
            {row.level ? t(`level.${row.level}`) : t('assessment.ungraded')}
          </Typography>
          {row.provisional && <Chip size="small" variant="outlined" label={t('assessment.provisional')} />}
        </Stack>
      </Tile>
      <Tile title={t('assessment.trend')} current={current} footer={asOfFooter(t, pick, row.method, 'trend')}>
        <Typography variant="h5" component="p">{row.trend ? t(`trend.${row.trend}`) : '—'}</Typography>
        {row.growth_rate != null && (
          <Typography variant="body2" color="text.secondary">
            {t('assessment.growth', { rate: pct(row.growth_rate), lower: pct(row.growth_lower), upper: pct(row.growth_upper) })}
          </Typography>
        )}
      </Tile>
    </Stack>
  )
}
