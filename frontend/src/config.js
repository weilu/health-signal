// Injected bootstrap (pre-login essentials); tolerate absence in dev.
export function getConfig() {
  const c = window.__HS_CONFIG__ || {}
  return {
    title: c.title || 'health-signal',
    branding: c.branding || {},
    defaultLocale: c.defaultLocale || 'en',
    locales: c.locales || ['en'],
    titles: c.titles || {},
  }
}

// The deployment's title in a language, from its own text; the configured title where it gives none.
export const siteTitle = (config, lng) => config.titles[lng] ?? config.title
