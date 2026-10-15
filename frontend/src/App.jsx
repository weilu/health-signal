import { useState } from 'react'
import { BrowserRouter, Routes, Route, NavLink, Navigate, useLocation } from 'react-router-dom'
import { AppBar, Toolbar, Typography, Button, Container, Box, Snackbar, Alert } from '@mui/material'
import { useTranslation } from 'react-i18next'
import ConfigView from './pages/ConfigView.jsx'
import LoginPage from './pages/LoginPage.jsx'
import { LocaleToggle } from './LocaleToggle.jsx'

// Inside the Router so useLocation works; the shell chrome reacts to the current route.
function Shell({ config }) {
  const { t } = useTranslation()
  const { pathname } = useLocation()
  const [logoutFailed, setLogoutFailed] = useState(false)

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

  const routes = (
    <Routes>
      <Route path="/login" element={<LoginPage config={config} />} />
      <Route path="/config" element={<ConfigView />} />
      {/* Land post-login '/' on the canonical page URL so nav highlighting matches. */}
      <Route path="/" element={<Navigate to="/config" replace />} />
      <Route path="*" element={<ConfigView />} />
    </Routes>
  )

  // Login is chrome-less (no AppBar): brand appears once, centered. /login is the only
  // unauthenticated route (httpOnly session has no client-readable flag).
  if (pathname === '/login') {
    return (
      <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', p: 2 }}>
        {routes}
      </Box>
    )
  }

  // NavLink sets the `.active` class + aria-current="page" when its route matches; MUI just styles it.
  return (
    <>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" component="h1" sx={{ flexGrow: 1 }}>{config.title}</Typography>
          <LocaleToggle locales={config.locales} color="inherit" sx={{ mr: 1 }} />
          <Button
            color="inherit"
            component={NavLink}
            to="/config"
            sx={{ borderRadius: 0, borderBottom: 2, borderColor: 'transparent', '&.active': { borderColor: 'currentColor' } }}
          >
            {t('nav.configuration')}
          </Button>
          <Button color="inherit" onClick={handleLogout}>{t('nav.logout')}</Button>
        </Toolbar>
      </AppBar>
      <Container component="main" sx={{ py: 3 }}>{routes}</Container>
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
