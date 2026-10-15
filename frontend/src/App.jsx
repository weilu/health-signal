import { BrowserRouter, Routes, Route, NavLink, Navigate, useLocation } from 'react-router-dom'
import { AppBar, Toolbar, Typography, Button, Container, Box } from '@mui/material'
import { useTranslation } from 'react-i18next'
import ConfigView from './pages/ConfigView.jsx'
import LoginPage from './pages/LoginPage.jsx'
import { LocaleToggle } from './LocaleToggle.jsx'

async function logout() {
  // Same-origin POST (CSRF-gated server-side); the 303 clears the cookie, then reload at /login.
  await fetch('/logout', { method: 'POST', credentials: 'same-origin', redirect: 'manual' }).catch(() => null)
  window.location.assign('/login')
}

// Inside the Router so useLocation works; the shell chrome reacts to the current route.
function Shell({ config }) {
  const { t } = useTranslation()
  const { pathname } = useLocation()
  const routes = (
    <Routes>
      <Route path="/login" element={<LoginPage config={config} />} />
      <Route path="/config" element={<ConfigView />} />
      {/* Land post-login '/' on the canonical page URL so nav highlighting matches. */}
      <Route path="/" element={<Navigate to="/config" replace />} />
      <Route path="*" element={<ConfigView />} />
    </Routes>
  )

  // Login is a standalone, chrome-less screen — no AppBar, so the brand appears once (in the card),
  // centered. Everything else gets the app shell. No client-readable auth flag (httpOnly session
  // cookie), so /login is the signal for "unauthenticated".
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
          <Button color="inherit" onClick={logout}>{t('nav.logout')}</Button>
        </Toolbar>
      </AppBar>
      <Container component="main" sx={{ py: 3 }}>{routes}</Container>
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
