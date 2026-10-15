import React from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource/ibm-plex-sans/400.css'
import '@fontsource/ibm-plex-sans/500.css'
import '@fontsource/ibm-plex-sans/600.css'
import { ThemeProvider, CssBaseline } from '@mui/material'
import { I18nextProvider } from 'react-i18next'
import { getConfig } from './config.js'
import { buildTheme } from './theme.js'
import { initI18n } from './i18n.js'
import App from './App.jsx'

const cfg = getConfig()
document.title = cfg.title
const i18n = initI18n({ defaultLocale: cfg.defaultLocale, locales: cfg.locales })
createRoot(document.getElementById('root')).render(
  <ThemeProvider theme={buildTheme(cfg.branding)}>
    <CssBaseline />
    <I18nextProvider i18n={i18n}><App config={cfg} /></I18nextProvider>
  </ThemeProvider>,
)
