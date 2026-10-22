import { useQueries, useQuery } from '@tanstack/react-query'
import { Link as RouterLink, useLocation } from 'react-router-dom'
import { Box, Chip, Paper, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { fetchAssessments, fetchPhaseStreams } from '../api.js'
import { assessmentParams, levelTone, pickInRange, sameSeries } from '../assessments.js'
import { panelParams, withFilters } from '../filters.js'
import { configLabel, weekStamp } from '../labels.js'
import { useMethod } from '../useMethod.js'
import { phaseQuery } from './PhasePanel.jsx'

export function SummaryPanel({ panel, target, location, range, latest }) {
  const { t } = useTranslation()
  const { search } = useLocation()
  const method = useMethod()
  const base = phaseQuery(target, location, method)
  const streams = useQuery({ queryKey: ['phase-streams', base], queryFn: () => fetchPhaseStreams(base), enabled: !!method })
  const entries = target.pages.flatMap((page) => page.panels
    .filter((p) => p.type === 'timeseries' && !p.series_by)
    .map((p) => ({ page, panel: p, params: { ...assessmentParams(panelParams(p.query, location?.value, range)), method: method?.name } })))
  // Same query keys as the panels' own tile lookups, so these share their cache.
  const results = useQueries({
    queries: entries.map((e) => ({ queryKey: ['assessments', e.params], queryFn: () => fetchAssessments(e.params), enabled: !!method })),
  })
  const rows = entries
    .map((e, i) => ({ ...e, data: results[i].data }))
    .filter((e) => e.data?.length)
  const title = configLabel(t, panel.label_key, panel.id)
  return (
    <Paper component="section" variant="outlined" aria-label={title} sx={{ p: 2 }}>
      <Typography variant="h6" component="h2" sx={{ mb: 1 }}>{title}</Typography>
      {!rows.length ? <Typography color="text.secondary">{t('summary.none')}</Typography> : (
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>{t('summary.indicator')}</TableCell>
                <TableCell>{t('summary.page')}</TableCell>
                <TableCell>{t('assessment.status')}</TableCell>
                <TableCell>{t('assessment.trend')}</TableCell>
                <TableCell>{t('summary.asOf')}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map(({ page, panel: p, data }) => {
                const pick = range ? pickInRange(data, range, latest) : null
                const row = pick?.row
                const stream = (streams.data ?? []).find((s) => sameSeries(p.query.feed, { indicator: p.query.indicator, ...p.query.dimensions }, s))
                return (
                  <TableRow key={`${page.id}/${p.id}`} hover selected={!!stream} component={RouterLink} to={withFilters(page.path, search)}
                    sx={{ textDecoration: 'none' }}>
                    <TableCell>
                      <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                        <span>{configLabel(t, p.label_key, p.id)}</span>
                        {stream && <Chip size="small" variant="outlined" label={t(`role.${stream.role}`, { defaultValue: stream.role })} />}
                      </Stack>
                    </TableCell>
                    <TableCell>{configLabel(t, page.label_key, page.id)}</TableCell>
                    <TableCell>
                      {row ? (
                        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                          <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: `${levelTone(method.levels, row.level)}.main` }} />
                          <span>{row.level ? t(`level.${row.level}`) : t('assessment.ungraded')}</span>
                        </Stack>
                      ) : '—'}
                    </TableCell>
                    <TableCell>{row?.trend ? t(`trend.${row.trend}`) : '—'}</TableCell>
                    <TableCell sx={{ color: pick?.current ? 'text.primary' : 'text.secondary' }}>
                      {row ? weekStamp(t, pick.asOf) : t('assessment.noneInRange')}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Paper>
  )
}
