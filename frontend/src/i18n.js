import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './locales/en.json'
import el from './locales/el.json'

export function initI18n({ defaultLocale = 'en' } = {}) {
  i18n.use(initReactI18next).init({
    resources: { en: { translation: en }, el: { translation: el } },
    lng: defaultLocale, fallbackLng: 'en', interpolation: { escapeValue: false },
  })
  return i18n
}
