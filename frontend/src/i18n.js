import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './locales/en.json'
import el from './locales/el.json'

export function initI18n({ defaultLocale = 'en' } = {}) {
  i18n.use(initReactI18next).init({
    resources: { en: { translation: en }, el: { translation: el } },
    lng: defaultLocale, fallbackLng: 'en', interpolation: { escapeValue: false },
  })
  // Reflect the RESOLVED language on <html lang> (after fallback) so an unsupported default like
  // 'fr' doesn't label English fallback content as French for assistive tech.
  if (typeof document !== 'undefined') {
    const applyLang = () => { document.documentElement.lang = i18n.resolvedLanguage || defaultLocale }
    applyLang()
    i18n.on('languageChanged', applyLang)
  }
  return i18n
}
