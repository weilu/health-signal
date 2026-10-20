import { useLocation, useNavigate } from 'react-router-dom'
import { ListSubheader, MenuItem, Stack, TextField } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { isCurrentYear, rangePresets, updateSearch, yearLabel } from './filters.js'
import { weekStamp } from './labels.js'
import { weekRange } from './weeks.js'

// Full-width rows on a phone; natural width side by side from sm up.
const field = (minWidth) => ({ size: 'small', select: true, sx: { minWidth, flex: { xs: '1 1 100%', sm: '0 0 auto' } } })

// Newest first, one group per ISO year; selects rather than <input type="week">, which Firefox and
// Safari render as free text.
function weekOptions(t, periods) {
  const weeks = weekRange(periods.first, periods.last).reverse()
  return weeks.flatMap((w, i) => {
    const item = <MenuItem key={w} value={w}>{weekStamp(t, w)}</MenuItem>
    return i === 0 || weeks[i - 1].slice(0, 4) !== w.slice(0, 4)
      ? [<ListSubheader key={`y${w}`}>{w.slice(0, 4)}</ListSubheader>, item]
      : [item]
  })
}

export function HeaderFilters({ locationFilter, location, locationLabel, rangeFilter, periods, range }) {
  const { t } = useTranslation()
  const { pathname, search } = useLocation()
  const navigate = useNavigate()
  const go = (changes) => navigate(pathname + updateSearch(search, changes))
  const setCustom = (a, b) => {
    const [from, to] = [a, b].sort()
    go({ range: null, from, to })
  }
  const presetLabel = (preset) => {
    if (preset === 'last') return t('range.last', { count: rangeFilter.default_weeks })
    if (preset === 'all') return t('range.all')
    const label = yearLabel(Number(preset.slice('year:'.length)), rangeFilter.year_start_week)
    return isCurrentYear(preset, rangeFilter, periods) ? t('range.current', { label }) : label
  }
  const presets = range ? rangePresets(rangeFilter, periods) : []
  const weeks = range ? weekOptions(t, periods) : []

  return (
    <Stack direction="row" useFlexGap sx={{ flexWrap: 'wrap', gap: 1.5 }}>
      {locationFilter && (
        <TextField {...field(160)} label={t('filters.location')} value={location} onChange={(e) => go({ location: e.target.value })}>
          {locationFilter.options.map((o) => <MenuItem key={o.value} value={o.value}>{locationLabel(o.value)}</MenuItem>)}
        </TextField>
      )}
      {range && (
        <>
          <TextField {...field(200)} label={t('filters.dateRange')} value={range.preset}
            onChange={(e) => go({ range: e.target.value, from: null, to: null })}>
            <ListSubheader>{t('range.quick')}</ListSubheader>
            {presets.filter((p) => !p.startsWith('year:')).map((p) => <MenuItem key={p} value={p}>{presetLabel(p)}</MenuItem>)}
            <ListSubheader>{t('range.years')}</ListSubheader>
            {presets.filter((p) => p.startsWith('year:')).map((p) => <MenuItem key={p} value={p}>{presetLabel(p)}</MenuItem>)}
            {/* Shown only as the current value, after the week pickers set one. */}
            <MenuItem value="custom" sx={{ display: 'none' }}>{t('range.custom')}</MenuItem>
          </TextField>
          {/* From/To share a row even on a phone. */}
          <Stack direction="row" useFlexGap sx={{ gap: 1.5, flex: { xs: '1 1 100%', sm: '0 0 auto' } }}>
            <TextField size="small" select label={t('range.from')} value={range.from} sx={{ minWidth: 132, flex: 1 }}
              onChange={(e) => setCustom(e.target.value, range.to)}>{weeks}</TextField>
            <TextField size="small" select label={t('range.to')} value={range.to} sx={{ minWidth: 132, flex: 1 }}
              onChange={(e) => setCustom(range.from, e.target.value)}>{weeks}</TextField>
          </Stack>
        </>
      )}
    </Stack>
  )
}
