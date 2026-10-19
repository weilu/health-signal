import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

// Bundle every ./locales/*.json; a new locale file is discovered here with no edit.
const modules = import.meta.glob('./locales/*.json', { eager: true })
const catalogs = Object.fromEntries(
  Object.entries(modules).map(([path, mod]) => [path.match(/\/([^/]+)\.json$/)[1], mod.default]),
)

const STORAGE_KEY = 'hs.locale'

// Register only the config-enabled locales, not every bundled file (an ['en'] deployment ships no 'el').
function pickResources(available, locales) {
  const resources = {}
  for (const lng of locales) {
    if (available[lng]) resources[lng] = { translation: available[lng] }
    else console.warn(`[i18n] config locale "${lng}" has no bundled catalog; skipping`)
  }
  return resources
}

// A stored locale, if still one the config enables; localStorage may throw (private mode) -> none.
function storedLocale(locales) {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    return locales.includes(v) ? v : null
  } catch {
    return null
  }
}

// Switch language and remember it across reloads; a storage failure is swallowed (nicety, not critical).
export function setLocale(lng) {
  i18n.changeLanguage(lng)
  try {
    localStorage.setItem(STORAGE_KEY, lng)
  } catch {
    /* storage unavailable (private mode) — skip persistence */
  }
}

// defaultLocale/locales are guaranteed non-empty upstream (server -> getConfig); no re-defaulting here.
export function initI18n({ defaultLocale, locales }) {
  i18n.use(initReactI18next).init({
    resources: pickResources(catalogs, locales),
    // A persisted choice wins over the config default; fallback follows the default, not hardcoded 'en'.
    lng: storedLocale(locales) || defaultLocale,
    fallbackLng: defaultLocale,
    interpolation: { escapeValue: false },
  })
  // Reflect the RESOLVED language (after fallback) on <html lang> for assistive tech.
  if (typeof document !== 'undefined') {
    const applyLang = () => { document.documentElement.lang = i18n.resolvedLanguage || defaultLocale }
    applyLang()
    i18n.on('languageChanged', applyLang)
  }
  return i18n
}
