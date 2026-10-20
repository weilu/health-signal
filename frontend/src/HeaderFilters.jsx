import { useId } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Box, ListSubheader, MenuItem, Stack, TextField, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { isCurrentYear, rangePresets, updateSearch, yearLabel } from './filters.js'
import { weekStamp } from './labels.js'
import { weekRange } from './weeks.js'

// Shrinks below its desktop width so both week pickers fit side by side on a phone.
const select = { size: 'small', select: true, sx: { minWidth: { xs: 0, sm: 160 }, flex: 1 } }

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

// Label/value rows after greece-public-health's header: Region, Date range, Reporting week.
export function HeaderFilters({ locationFilter, location, locationLabel, rangeFilter, periods, range }) {
  const { t } = useTranslation()
  const { pathname, search } = useLocation()
  const navigate = useNavigate()
  const ids = { region: useId(), range: useId() }
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
  const quick = presets.filter((p) => !p.startsWith('year:'))
  const years = presets.filter((p) => p.startsWith('year:'))
  const weeks = range ? weekOptions(t, periods) : []
  const label = (id, text) => <Typography id={id} variant="body2" color="text.secondary">{text}</Typography>

  return (
    <Box sx={{ display: 'grid', gridTemplateColumns: { xs: 'minmax(0, 1fr)', sm: 'auto minmax(0, 1fr)' }, columnGap: 2, rowGap: { xs: 0.5, sm: 1 }, alignItems: 'center' }}>
      {locationFilter && (
        <>
          {label(ids.region, t('filters.location'))}
          <TextField {...select} value={location} onChange={(e) => go({ location: e.target.value })}
            slotProps={{ select: { labelId: ids.region } }}>
            {locationFilter.options.map((o) => <MenuItem key={o.value} value={o.value}>{locationLabel(o.value)}</MenuItem>)}
          </TextField>
        </>
      )}
      {range && (
        <>
          {label(ids.range, t('filters.dateRange'))}
          <Stack spacing={1}>
            <TextField {...select} value={range.preset} onChange={(e) => go({ range: e.target.value, from: null, to: null })}
              slotProps={{ select: { labelId: ids.range } }}>
              <ListSubheader>{t('range.quick')}</ListSubheader>
              {quick.map((p) => <MenuItem key={p} value={p}>{presetLabel(p)}</MenuItem>)}
              <ListSubheader>{t('range.years')}</ListSubheader>
              {years.map((p) => <MenuItem key={p} value={p}>{presetLabel(p)}</MenuItem>)}
              {/* Shown only as the current value, after the week pickers set one. */}
              <MenuItem value="custom" sx={{ display: 'none' }}>{t('range.custom')}</MenuItem>
            </TextField>
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
              <TextField {...select} value={range.from} onChange={(e) => setCustom(e.target.value, range.to)}
                slotProps={{ htmlInput: { 'aria-label': t('range.from') } }}>{weeks}</TextField>
              <Typography aria-hidden="true" color="text.secondary">–</Typography>
              <TextField {...select} value={range.to} onChange={(e) => setCustom(range.from, e.target.value)}
                slotProps={{ htmlInput: { 'aria-label': t('range.to') } }}>{weeks}</TextField>
            </Stack>
          </Stack>
          {label(undefined, t('filters.reportingWeek'))}
          <Typography variant="body2" fontWeight={500}>{weekStamp(t, periods.last)}</Typography>
        </>
      )}
    </Box>
  )
}
