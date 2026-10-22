import { Box, Chip, Paper, Stack, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { weekStamp } from '../labels.js'
import { levelTone } from '../assessments.js'

const pct = (v) => `${v > 0 ? '+' : ''}${Math.round(v * 100)}%`

// Not-current tiles are dashed and muted so a past state isn't read as now (spec §9).
export function Tile({ title, current, footer, children }) {
  return (
    <Paper variant="outlined" sx={{ p: 1.5, flex: 1, opacity: current ? 1 : 0.75, borderStyle: current ? 'solid' : 'dashed' }}>
      <Typography variant="overline" color="text.secondary" component="p">{title}</Typography>
      {children}
      <Typography variant="caption" color="text.secondary" component="p">{footer}</Typography>
    </Paper>
  )
}

export function NoneInRange() {
  const { t } = useTranslation()
  return (
    <Paper variant="outlined" sx={{ p: 1.5 }}>
      <Typography variant="body2" color="text.secondary">{t('assessment.noneInRange')}</Typography>
    </Paper>
  )
}

export function asOfFooter(t, pick, method) {
  return t(pick.current ? 'assessment.asOf' : 'assessment.asOfPast', { week: weekStamp(t, pick.asOf), method })
}

export function StatusTrendTiles({ pick, method }) {
  const { t } = useTranslation()
  if (!pick.row) return <NoneInRange />
  const { row, current } = pick
  const footer = asOfFooter(t, pick, row.method)
  return (
    <Stack direction={{ xs: 'row', md: 'column' }} spacing={1.5} useFlexGap>
      <Tile title={t('assessment.status')} current={current} footer={footer}>
        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
          <Box sx={{ width: 10, height: 10, borderRadius: '50%', flexShrink: 0, bgcolor: `${levelTone(method.levels, row.level)}.main` }} />
          <Typography variant="h6" component="p">{row.level ? t(`level.${row.level}`) : t('assessment.ungraded')}</Typography>
          {row.provisional && <Chip size="small" variant="outlined" label={t('assessment.provisional')} />}
        </Stack>
      </Tile>
      <Tile title={t('assessment.trend')} current={current} footer={footer}>
        <Typography variant="h6" component="p">{row.trend ? t(`trend.${row.trend}`) : '—'}</Typography>
        {row.growth_rate != null && (
          <Typography variant="body2" color="text.secondary">
            {t('assessment.growth', { rate: pct(row.growth_rate), lower: pct(row.growth_lower), upper: pct(row.growth_upper) })}
          </Typography>
        )}
      </Tile>
    </Stack>
  )
}
