import { Box, Chip, Stack } from '@mui/material'

// The legend of a chart split into several lines, as buttons: a reader turns lines on and off, by mouse or keyboard,
// where a click on Chart.js's canvas legend couldn't be reached by keyboard.
export function SeriesToggles({ series, colours, hidden, onToggle }) {
  return (
    <Stack direction="row" useFlexGap sx={{ flexWrap: 'wrap', gap: 0.75, mb: 1 }}>
      {series.map((s, i) => {
        const shown = !hidden.has(s.key)
        return (
          <Chip key={s.key} size="small" label={s.label} aria-pressed={shown} onClick={() => onToggle(s.key)}
            variant={shown ? 'filled' : 'outlined'}
            sx={{ color: shown ? 'text.primary' : 'text.secondary' }}
            icon={<Box component="span" aria-hidden sx={{ width: 14, height: 3, borderRadius: 1, ml: 0.75,
                                                          bgcolor: shown ? colours[i] : 'divider' }} />} />
        )
      })}
    </Stack>
  )
}
