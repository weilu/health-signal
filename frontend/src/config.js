// Injected bootstrap (pre-login essentials); tolerate absence in dev.
export function getConfig() {
  const c = window.__HS_CONFIG__ || {}
  return {
    title: c.title || 'health-signal',
    branding: c.branding || {},
    defaultLocale: c.defaultLocale || 'en',
    locales: c.locales || ['en'],
  }
}
