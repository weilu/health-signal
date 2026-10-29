import { useQueries, useQuery } from '@tanstack/react-query'
import { Navigate, Link as RouterLink, useLocation } from 'react-router-dom'
import { Alert, Box, Chip, CircularProgress, Link, Paper, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { fetchAssessments, fetchPhaseStreams } from '../api.js'
import { combinedState, levelTone, pickInRange, sameSeries, toneColor } from '../assessments.js'
import { panelParams, withFilters } from '../filters.js'
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
  const groups = groupRows(t, rows)
  if (state === 'unauth') return <Navigate to="/login" replace />
  return (
    <Paper component="section" variant="outlined" aria-label={title} sx={{ p: 2 }}>
      <Typography variant="h6" component="h2" sx={{ mb: 1 }}>{title}</Typography>
      {state === 'loading' ? <CircularProgress aria-label={t('app.loading')} />
        : state === 'error' ? <Alert severity="error">{t('app.error')}</Alert>
        : !rows.length ? <Typography color="text.secondary">{t('summary.none')}</Typography> : (
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>{t('summary.indicator')}</TableCell>
                <TableCell sx={WIDE}>{t('assessment.status')}</TableCell>
                <TableCell sx={WIDE}>{t('assessment.trend')}</TableCell>
                <TableCell sx={WIDE}>{t('summary.asOf')}</TableCell>
              </TableRow>
            </TableHead>
            {groups.map(({ key, label, rows: members }) => (
            <TableBody key={key}>
              <TableRow>
                <TableCell component="th" scope="rowgroup" colSpan={4} sx={{ fontWeight: 600, color: 'text.secondary' }}>
                  {label}
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
                  // A real row with a real link, stretched over the row so the whole row is clickable.
                  <TableRow key={`${page.id}/${p.id}`} hover selected={!!stream} sx={{ position: 'relative' }}>
                    <TableCell>
                      <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                        <Link component={RouterLink} to={withFilters(page.path, search)} underline="hover" color="inherit"
                          sx={{ '&::after': { content: '""', position: 'absolute', inset: 0 } }}>
                          {configLabel(t, p.label_key, p.id)}
                        </Link>
                        {stream && <Chip size="small" variant="outlined" label={t(`role.${stream.role}`, { defaultValue: stream.role })} />}
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

// Subheadings: the feed, then its kind only where the feed has both
// (pathogen-specific vs syndromic clinical), and the tabs a series is shared across.
function groupRows(t, rows) {
  const kinds = new Map()
  for (const { panel: p } of rows) {
    const feed = p.group?.feed ?? p.query.feed
    kinds.set(feed, (kinds.get(feed) ?? new Set()).add(p.group?.kind))
  }
  const groups = new Map()
  for (const r of rows) {
    const g = r.panel.group ?? { feed: r.panel.query.feed, targets: [] }
    const key = `${g.feed}.${g.kind}.${g.targets.join('/')}`
    if (!groups.has(key)) {
      const shared = g.targets.length > 1
        && t('summary.sharedAcross', { targets: g.targets.map((id) => configLabel(t, `targets.${id}`, id)).join(' / ') })
      const label = [t(`feeds.${g.feed}`, { defaultValue: g.feed }), kinds.get(g.feed).size > 1 && t(`summary.group.${g.kind}`), shared]
        .filter(Boolean).join(' · ')
      groups.set(key, { key, label, rows: [] })
    }
    groups.get(key).rows.push(r)
  }
  return [...groups.values()]
}
