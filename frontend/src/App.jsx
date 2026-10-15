import { useState } from 'react'
import { BrowserRouter, Routes, Route, NavLink, Navigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { AppBar, Toolbar, Typography, Button, Container, Box, Snackbar, Alert } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { fetchConfig } from './api.js'
import { ResourceBoundary } from './ResourceBoundary.jsx'
import ConfigView from './pages/ConfigView.jsx'
import LoginPage from './pages/LoginPage.jsx'
import TargetPage from './pages/TargetPage.jsx'
import { LocaleToggle } from './LocaleToggle.jsx'

const navSx = { borderRadius: 0, borderBottom: 2, borderColor: 'transparent', '&.active': { borderColor: 'currentColor' } }

function AppRoutes({ view }) {
  const { t } = useTranslation()
  const pages = view.targets.flatMap((target) => target.pages.map((page) => ({ target, page })))
  const home = pages[0]?.page.path ?? '/config'
  return (
    <Routes>
      {pages.map(({ target, page }) => (
        <Route key={page.path} path={page.path} element={<TargetPage target={target} page={page} />} />
      ))}
      <Route path="/config" element={<ConfigView />} />
      <Route path="/" element={<Navigate to={home} replace />} />
      <Route path="*" element={<Alert severity="info">{t('app.notFound')}</Alert>} />
    </Routes>
  )
}

// Inside the Router so useLocation works; the shell chrome reacts to the current route.
function Shell({ config }) {
  const { t } = useTranslation()
  const { pathname } = useLocation()
  const [logoutFailed, setLogoutFailed] = useState(false)
  const onLogin = pathname === '/login'
  const configQuery = useQuery({ queryKey: ['config'], queryFn: fetchConfig, enabled: !onLogin })

  async function handleLogout() {
    // Only the server can clear the httpOnly cookie, so redirect only on a confirmed 303 — otherwise
    // the session is still valid and /login would falsely imply a sign-out.
    const res = await fetch('/logout', { method: 'POST', credentials: 'same-origin', redirect: 'manual' }).catch(() => null)
    if (res && (res.ok || res.type === 'opaqueredirect' || res.status === 303)) {
      window.location.assign('/login')
      return
    }
    setLogoutFailed(true)
  }

  // Login is chrome-less (no AppBar): brand appears once, centered. /login is the only
  // unauthenticated route (httpOnly session has no client-readable flag).
  if (onLogin) {
    return (
      <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', p: 2 }}>
        <LoginPage config={config} />
      </Box>
    )
  }

  // NavLink sets `.active` + aria-current="page"; without `end`, nested page paths keep their target's tab active.
  const targets = (configQuery.data?.targets ?? []).filter((target) => target.pages.length)
  return (
    <>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" component="h1" sx={{ flexGrow: 1 }}>{config.title}</Typography>
          {targets.map((target) => (
            <Button key={target.id} color="inherit" component={NavLink} to={target.pages[0].path} sx={navSx}>
              {t(target.label_key, { defaultValue: target.id })}
            </Button>
          ))}
          <Button color="inherit" component={NavLink} to="/config" sx={navSx}>{t('nav.configuration')}</Button>
          <LocaleToggle locales={config.locales} color="inherit" sx={{ ml: 1 }} />
          <Button color="inherit" onClick={handleLogout}>{t('nav.logout')}</Button>
        </Toolbar>
      </AppBar>
      <Container component="main" sx={{ py: 3 }}>
        <ResourceBoundary query={configQuery}>{(view) => <AppRoutes view={view} />}</ResourceBoundary>
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
