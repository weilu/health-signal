import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './locales/en.json'
import el from './locales/el.json'

export function initI18n({ defaultLocale = 'en' } = {}) {
  i18n.use(initReactI18next).init({
    resources: { en: { translation: en }, el: { translation: el } },
    lng: defaultLocale, fallbackLng: 'en', interpolation: { escapeValue: false },
  })
  // Reflect the active language on <html lang> so assistive tech reads the page correctly.
  if (typeof document !== 'undefined') {
    document.documentElement.lang = i18n.language || defaultLocale
    i18n.on('languageChanged', (lng) => { document.documentElement.lang = lng })
  }
  return i18n
}
