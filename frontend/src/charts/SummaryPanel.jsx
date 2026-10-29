import { useQueries, useQuery } from '@tanstack/react-query'
import { Navigate, Link as RouterLink, useLocation } from 'react-router-dom'
import { Alert, Box, Chip, CircularProgress, Link, Paper, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { fetchAssessments, fetchPhaseStreams } from '../api.js'
import { combinedState, levelTone, pickInRange, sameSeries, toneColor } from '../assessments.js'
import { panelParams, withFilters } from '../filters.js'
import { groupPanels } from '../groups.js'
import { configLabel, weekStamp } from '../labels.js'
import { useMethod } from '../useMethod.js'
import { phaseQuery } from './PhasePanel.jsx'

// Phones get one column, with status, trend and as-of on a line under the indicator, instead of three more.
const WIDE = { display: { xs: 'none', md: 'table-cell' } }
const NARROW = { display: { xs: 'flex', md: 'none' } }

export function SummaryPanel({ panel, target, location, range, latest }) {
  const { t } = useTranslation()
  const { search } = useLocation()
  const method = useMethod()
  const base = phaseQuery(target, location, method)
  const streams = useQuery({ queryKey: ['phase-streams', base], queryFn: () => fetchPhaseStreams(base), enabled: !!method })
  const entries = target.pages.flatMap((page) => page.panels
    .filter((p) => p.type === 'timeseries' && !p.series_by)
    .map((p) => ({ page, panel: p, params: { ...panelParams(p.query, location?.value), method: method?.name } })))
  // Same query keys as the panels' own tile lookups, so these share their cache.
  const results = useQueries({
    queries: entries.map((e) => ({ queryKey: ['assessments', e.params], queryFn: () => fetchAssessments(e.params), enabled: !!method })),
  })
  const state = method ? combinedState([...results, streams]) : 'loading'
  const rows = entries
    .map((e, i) => ({ ...e, data: results[i].data }))
    .filter((e) => e.data?.length)
  const title = configLabel(t, panel.label_key, panel.id)
  const groups = groupPanels(t, rows, { panelOf: (r) => r.panel, alwaysSource: true })
  if (state === 'unauth') return <Navigate to="/login" replace />
  return (
    <Paper component="section" variant="outlined" aria-label={title} sx={{ p: 2 }}>
      <Typography variant="h6" component="h2" sx={{ mb: 1 }}>{title}</Typography>
      {state === 'loading' ? <CircularProgress aria-label={t('app.loading')} />
        : state === 'error' ? <Alert severity="error">{t('app.error')}</Alert>
        : !rows.length ? <Typography color="text.secondary">{t('summary.none')}</Typography> : (
        <TableContainer>
          <Table size="small">
            {/* The column labels frame every section, so they carry the table's one shaded band; the sections below are
                labels set off by space and a rule, never stronger than this. One column on phones. */}
            <TableHead sx={{ display: { xs: 'none', md: 'table-header-group' } }}>
              <TableRow sx={{ '& > th': { typography: 'body2', fontWeight: 600, color: 'text.secondary', bgcolor: 'background.default',
                                          borderBottom: 1, borderColor: 'divider' } }}>
                <TableCell>{t('summary.indicator')}</TableCell>
                <TableCell>{t('assessment.status')}</TableCell>
                <TableCell>{t('assessment.trend')}</TableCell>
                <TableCell>{t('summary.asOf')}</TableCell>
              </TableRow>
            </TableHead>
            {groups.map(({ key, heading: { source, kind, shared }, items: members }) => (
            <TableBody key={key}>
              <TableRow>
                {/* A section is a semibold label with room above it and an ink rule under it; rows get hairlines. */}
                <TableCell component="th" scope="rowgroup" colSpan={4}
                  sx={{ pt: 2.5, pb: 0.75, typography: 'body2', borderBottom: 1, borderColor: 'text.secondary' }}>
                  <Stack direction={{ xs: 'column', md: 'row' }} sx={{ columnGap: 1, justifyContent: 'space-between' }}>
                    <Box>
                      <Box component="span" data-part sx={{ fontWeight: 600, color: 'text.primary' }}>{source}</Box>
                      {kind && <Box component="span" data-part sx={{ ml: 1, color: 'text.secondary' }}>{kind}</Box>}
                    </Box>
                    {shared && <Box component="span" data-part sx={{ typography: 'caption', color: 'text.secondary' }}>{shared}</Box>}
                  </Stack>
                </TableCell>
              </TableRow>
              {members.map(({ page, panel: p, data }) => {
                const pick = range ? pickInRange(data, range, latest) : null
                const row = pick?.row
                // The stream's own location too: without a location filter, another region's row has the same selector.
                const stream = !pick?.ambiguous && (streams.data ?? []).find((s) => s.location === data[0].location
                  && sameSeries(p.query.feed, { indicator: p.query.indicator, ...p.query.dimensions }, s))
                const status = pick?.ambiguous ? t('assessment.ambiguous')
                  : row ? (row.level ? t(`level.${row.level}`) : t('assessment.ungraded')) : '—'
                const trend = row?.trend ? t(`trend.${row.trend}`) : '—'
                const asOf = pick?.ambiguous ? '—' : row ? weekStamp(t, pick.asOf) : t('assessment.noneInRange')
                const dot = row && !pick?.ambiguous && (
                  <Box sx={{ width: 10, height: 10, borderRadius: '50%', flexShrink: 0, bgcolor: toneColor(levelTone(method.levels, row.level)) }} />
                )
                return (
                  // A real row with a real link, stretched over the row so the whole row is clickable. A stream is
                  // marked by its role chip alone: the amber there is the table's one accent.
                  <TableRow key={`${page.id}/${p.id}`} hover
                    sx={{ position: 'relative', '& > td': { borderBottom: 1, borderColor: 'divider' },
                          '&:last-of-type > td': { borderBottom: 0 } }}>
                    <TableCell>
                      <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                        <Link component={RouterLink} to={withFilters(page.path, search)} underline="hover" color="inherit"
                          sx={{ '&::after': { content: '""', position: 'absolute', inset: 0 } }}>
                          {configLabel(t, p.label_key, p.id)}
                        </Link>
                        {stream && <Chip size="small" variant="outlined" color="primary" label={t(`role.${stream.role}`, { defaultValue: stream.role })} />}
                      </Stack>
                      <Stack direction="row" spacing={1} sx={{ ...NARROW, alignItems: 'center', mt: 0.5, color: 'text.secondary' }}>
                        {dot}
                        <Typography variant="body2" component="span">{[status, trend, asOf].join(' · ')}</Typography>
                      </Stack>
                    </TableCell>
                    <TableCell sx={WIDE}>
                      <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>{dot}<span>{status}</span></Stack>
                    </TableCell>
                    <TableCell sx={WIDE}>{trend}</TableCell>
                    <TableCell sx={{ ...WIDE, color: pick?.current ? 'text.primary' : 'text.secondary' }}>{asOf}</TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
            ))}
          </Table>
        </TableContainer>
      )}
    </Paper>
  )
}
