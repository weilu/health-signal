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

// Full client view-model (authenticated) from the gated endpoint. 401 -> caller shows login CTA.
export async function fetchConfig() {
  const res = await fetch('/api/config', { credentials: 'same-origin' })
  if (res.status === 401) { const e = new Error('unauthenticated'); e.status = 401; throw e }
  if (!res.ok) throw new Error(`config fetch failed: ${res.status}`)
  return res.json()
}
