import React from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource/ibm-plex-sans/400.css'
import '@fontsource/ibm-plex-sans/500.css'
import '@fontsource/ibm-plex-sans/600.css'
import { ThemeProvider, CssBaseline } from '@mui/material'
import { I18nextProvider } from 'react-i18next'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { getConfig, siteTitle } from './config.js'
import { buildTheme } from './theme.js'
import { initI18n } from './i18n.js'
import App from './App.jsx'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (count, err) => err?.status !== 401 && count < 2,  // a 401 won't fix itself
      staleTime: 5 * 60 * 1000,  // weekly data: no refetch on every page switch
    },
  },
})

const cfg = getConfig()
const i18n = initI18n({ defaultLocale: cfg.defaultLocale, locales: cfg.locales })
// The browser tab follows the language, like the header.
const applyTitle = () => { document.title = siteTitle(cfg, i18n.resolvedLanguage) }
applyTitle()
i18n.on('languageChanged', applyTitle)
createRoot(document.getElementById('root')).render(
  <ThemeProvider theme={buildTheme(cfg.branding)}>
    <CssBaseline />
    <I18nextProvider i18n={i18n}>
      <QueryClientProvider client={queryClient}><App config={cfg} /></QueryClientProvider>
    </I18nextProvider>
  </ThemeProvider>,
)
