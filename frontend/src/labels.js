// A config label: its i18n key if set (the id when untranslated), else the id. i18next returns ""
// for t(null) instead of the default, so a missing key must never reach t.
export const configLabel = (t, key, id) => (key ? t(key, { defaultValue: id }) : id)
