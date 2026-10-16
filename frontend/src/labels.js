// i18next returns "" for t(null) instead of the default, so a missing key never reaches t.
export const configLabel = (t, key, id) => (key ? t(key, { defaultValue: id }) : id)
