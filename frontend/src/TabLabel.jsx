import { Box, SvgIcon } from '@mui/material'

// A padlock after the name marks a tab behind the sign-in, so a reader can tell it from a public one.
export function TabLabel({ label, lock }) {
  if (!lock) return label
  return (
    <Box component="span" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.75 }}>
      {label}
      <SvgIcon titleAccess={lock} viewBox="0 0 11 13" sx={{ fontSize: '0.8em', color: 'text.secondary' }}>
        <path d="M2.6 6V3.8C2.6 2.26 3.89 1 5.5 1S8.4 2.26 8.4 3.8V6" stroke="currentColor" strokeWidth="1.1" fill="none" />
        <rect x="1.2" y="6" width="8.6" height="6" rx="0.6" />
      </SvgIcon>
    </Box>
  )
}
