import { Box, Paper, TextField, Button, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'

export default function LoginPage({ config }) {
  const { t } = useTranslation()
  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', mt: 6 }}>
      <Paper sx={{ p: 4, width: 360 }} elevation={2}>
        <Typography variant="h5" gutterBottom>{config.title}</Typography>
        <Typography variant="subtitle1" gutterBottom>{t('login.title')}</Typography>
        {/* Native POST: server sets the session and 303-redirects to '/', which reloads with the full config. */}
        <form method="post" action="/login">
          <TextField name="email" type="email" label={t('login.email')} fullWidth required margin="normal" />
          <TextField name="password" type="password" label={t('login.password')} fullWidth required margin="normal" />
          <Button type="submit" variant="contained" fullWidth sx={{ mt: 2 }}>{t('login.submit')}</Button>
        </form>
      </Paper>
    </Box>
  )
}
