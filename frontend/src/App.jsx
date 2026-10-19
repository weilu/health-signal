import { useState } from 'react'
import { BrowserRouter, Routes, Route, NavLink, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { AppBar, Toolbar, Typography, Button, Container, Box, Snackbar, Alert, MenuItem, Tab, Tabs, TextField } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { fetchConfig } from './api.js'
import { ResourceBoundary } from './ResourceBoundary.jsx'
import ConfigView from './pages/ConfigView.jsx'
import LoginPage from './pages/LoginPage.jsx'
import TargetPage from './pages/TargetPage.jsx'
import { LocaleToggle } from './LocaleToggle.jsx'
import { configLabel } from './labels.js'
import { activePage } from './nav.js'
import { selectedLocation, withLocation } from './filters.js'

const rule = { borderBottom: 1, borderColor: 'divider' }

function AppRoutes({ view, location }) {
  const { t } = useTranslation()
  const pages = view.targets.flatMap((target) => target.pages.map((page) => ({ target, page })))
  const home = pages[0]?.page.path ?? '/config'
  return (
    <Routes>
      {pages.map(({ page }) => (
        // Keyed by path: react-router reuses unkeyed elements, carrying panel state across pages.
        <Route key={page.path} path={page.path} element={<TargetPage key={page.path} page={page} location={location} />} />
      ))}
      <Route path="/config" element={<ConfigView />} />
      <Route path="/" element={<Navigate to={withLocation(home, location?.value)} replace />} />
      <Route path="*" element={<Alert severity="info">{t('app.notFound')}</Alert>} />
    </Routes>
  )
}

// Inside the Router so useLocation works.
function Shell({ config }) {
  const { t } = useTranslation()
  const { pathname, search } = useLocation()
  const navigate = useNavigate()
  const [logoutFailed, setLogoutFailed] = useState(false)
  const onLogin = pathname === '/login'
  const configQuery = useQuery({ queryKey: ['config'], queryFn: fetchConfig, enabled: !onLogin })

  async function handleLogout() {
    // Only the server can clear the httpOnly cookie, so redirect only on a confirmed 303.
    const res = await fetch('/logout', { method: 'POST', credentials: 'same-origin', redirect: 'manual' }).catch(() => null)
    if (res && (res.ok || res.type === 'opaqueredirect' || res.status === 303)) {
      window.location.assign('/login')
      return
    }
    setLogoutFailed(true)
  }

  // /login is chrome-less and the only unauthenticated route (no client-readable session flag).
  if (onLogin) {
    return (
      <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', p: 2 }}>
        <LoginPage config={config} />
      </Box>
    )
  }

  // Layout after greece-public-health: header, target tabs, then page tabs for multi-page targets.
  const targets = (configQuery.data?.targets ?? []).filter((target) => target.pages.length)
  const active = activePage(targets, pathname)
  const locationFilter = configQuery.data?.filters?.location ?? null
  const location = selectedLocation(locationFilter, search)
  const locationLabel = (value) => configLabel(t, locationFilter?.options.find((o) => o.value === value)?.label_key, value)
  return (
    <>
      <AppBar position="static" color="transparent" elevation={0} sx={rule}>
        <Container maxWidth="xl">
          <Toolbar disableGutters>
            <Typography variant="h5" component="h1" sx={{ flexGrow: 1 }}>{config.title}</Typography>
            {locationFilter && (
              <TextField select size="small" label={t('filters.location')} value={location} sx={{ mr: 2 }}
                onChange={(e) => navigate(withLocation(pathname, e.target.value))}>
                {locationFilter.options.map((o) => <MenuItem key={o.value} value={o.value}>{locationLabel(o.value)}</MenuItem>)}
              </TextField>
            )}
            <LocaleToggle locales={config.locales} sx={{ mr: 1 }} />
            {/* Outside the tab rows, so the selected state is styled off NavLink's aria-current. */}
            <Button component={NavLink} to={withLocation('/config', location)} sx={{ mr: 1, '&[aria-current="page"]': { bgcolor: 'action.selected' } }}>
              {t('nav.configuration')}
            </Button>
            <Button onClick={handleLogout}>{t('nav.logout')}</Button>
          </Toolbar>
        </Container>
      </AppBar>
      <Box component="nav" aria-label={t('config.targets')} sx={rule}>
        <Container maxWidth="xl">
          <Tabs value={active?.target.id ?? false} variant="scrollable" allowScrollButtonsMobile>
            {targets.map((target) => (
              <Tab key={target.id} value={target.id} component={NavLink} end to={withLocation(target.pages[0].path, location)}
                label={configLabel(t, target.label_key, target.id)} sx={{ typography: 'h6' }} />
            ))}
          </Tabs>
        </Container>
      </Box>
      {active && active.target.pages.length > 1 && (
        <Box component="nav" aria-label={configLabel(t, active.target.label_key, active.target.id)} sx={{ ...rule, bgcolor: 'background.paper' }}>
          <Container maxWidth="xl">
            <Tabs value={active.page.path} variant="scrollable" allowScrollButtonsMobile>
              {active.target.pages.map((p) => (
                <Tab key={p.path} value={p.path} component={NavLink} end to={withLocation(p.path, location)} label={configLabel(t, p.label_key, p.id)} />
              ))}
            </Tabs>
          </Container>
        </Box>
      )}
      <Container component="main" maxWidth="xl" sx={{ py: 3 }}>
        <ResourceBoundary query={configQuery}>
          {(view) => <AppRoutes view={view} location={location && { value: location, label: locationLabel(location) }} />}
        </ResourceBoundary>
      </Container>
      <Snackbar open={logoutFailed} autoHideDuration={6000} onClose={() => setLogoutFailed(false)}>
        <Alert severity="error" onClose={() => setLogoutFailed(false)}>{t('app.logoutError')}</Alert>
      </Snackbar>
    </>
  )
}

export default function App({ config }) {
  return (
    <BrowserRouter>
      <Shell config={config} />
    </BrowserRouter>
  )
}
