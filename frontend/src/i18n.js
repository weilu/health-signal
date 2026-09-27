import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

// Bundle every ./locales/*.json; a new locale file is discovered here with no edit.
const modules = import.meta.glob('./locales/*.json', { eager: true })
const catalogs = Object.fromEntries(
  Object.entries(modules).map(([path, mod]) => [path.match(/\/([^/]+)\.json$/)[1], mod.default]),
)

// Register only the config-enabled locales, not every bundled file (an ['en'] deployment ships no 'el').
export function pickResources(available, locales) {
  const resources = {}
  for (const lng of locales) {
    if (available[lng]) resources[lng] = { translation: available[lng] }
    else console.warn(`[i18n] config locale "${lng}" has no bundled catalog; skipping`)
  }
  return resources
}

// defaultLocale/locales are guaranteed non-empty upstream (server -> getConfig); no re-defaulting here.
export function initI18n({ defaultLocale, locales }) {
  i18n.use(initReactI18next).init({
    resources: pickResources(catalogs, locales),
    // Fallback follows the deployment's default, not a hardcoded 'en'.
    lng: defaultLocale, fallbackLng: defaultLocale, interpolation: { escapeValue: false },
  })
  // Reflect the RESOLVED language (after fallback) on <html lang> for assistive tech.
  if (typeof document !== 'undefined') {
    const applyLang = () => { document.documentElement.lang = i18n.resolvedLanguage || defaultLocale }
    applyLang()
    i18n.on('languageChanged', applyLang)
  }
  return i18n
}
