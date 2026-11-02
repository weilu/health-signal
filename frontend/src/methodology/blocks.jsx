import { Box, Typography } from '@mui/material'
import { alpha } from '@mui/material/styles'
import { useTranslation } from 'react-i18next'

// Shaded with an amber edge, so a reader tells what the dashboard's settings say from the team's own reasoning.
export function GeneratedBox({ caption, children }) {
  return (
    <Box sx={(theme) => ({ my: 2, px: 2, py: 1.5, borderLeft: 3, borderColor: 'warning.main', borderRadius: 0.5,
                           bgcolor: alpha(theme.palette.warning.main, 0.08) })}>
      <Typography variant="caption" color="text.secondary" component="p" sx={{ mb: 1 }}>{caption}</Typography>
      {children}
    </Box>
  )
}

export function Block({ name }) {
  const { t } = useTranslation()
  return <GeneratedBox caption={t(`methodology.caption.${name}`, { defaultValue: name })} />
}
