import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import { AppBar, Toolbar, Typography, Button, Container } from '@mui/material'
import { useTranslation } from 'react-i18next'
import ConfigView from './pages/ConfigView.jsx'
import LoginPage from './pages/LoginPage.jsx'

export default function App({ config }) {
  const { t } = useTranslation()
  return (
    <BrowserRouter>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>{config.title}</Typography>
          <Button color="inherit" component={Link} to="/config">{t('nav.configuration')}</Button>
        </Toolbar>
      </AppBar>
      <Container component="main" sx={{ py: 3 }}>
        <Routes>
          <Route path="/login" element={<LoginPage config={config} />} />
          <Route path="/config" element={<ConfigView />} />
          <Route path="*" element={<ConfigView />} />
        </Routes>
      </Container>
    </BrowserRouter>
  )
}
