import { Box, Button } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { setLocale } from './i18n.js'

// Language switcher for the AppBar and login card; hidden with <2 locales. `color` matches the surface.
export function LocaleToggle({ locales = [], color, sx }) {
  const { i18n } = useTranslation()
  if (locales.length < 2) return null
  return (
    <Box sx={sx}>
      {locales.map((lng) => (
        <Button
          key={lng}
          size="small"
          color={color}
          onClick={() => setLocale(lng)}
          aria-pressed={i18n.resolvedLanguage === lng}
          variant={i18n.resolvedLanguage === lng ? 'outlined' : 'text'}
          sx={{ minWidth: 0, ml: 0.5 }}
        >
          {lng.toUpperCase()}
        </Button>
      ))}
    </Box>
  )
}
