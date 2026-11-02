import { useQuery } from '@tanstack/react-query'
import { Box, Table, TableBody, TableCell, TableHead, TableRow, Typography } from '@mui/material'
import { alpha } from '@mui/material/styles'
import { useTranslation } from 'react-i18next'
import { fetchConfig } from '../api.js'
import { levelTone } from '../assessments.js'
import { ToneDot } from '../charts/TrendMark.jsx'
import { configLabel, inSentence, panelLabel } from '../labels.js'

// Shaded with an amber edge, so a reader tells what the dashboard's settings say from the team's own reasoning.
export function GeneratedBox({ caption, children }) {
  return (
    <Box sx={(theme) => ({ my: 2, px: 2, py: 1.5, borderLeft: 3, borderColor: 'warning.main', borderRadius: 0.5,
                           bgcolor: alpha(theme.palette.warning.main, 0.08) })}>
      <Typography variant="caption" color="text.secondary" component="p" sx={{ mb: 1 }}>{caption}</Typography>
      {children}
    </Box>
  )
}

function Grid({ head, children }) {
  return (
    <Table size="small" sx={{ '& td, & th': { px: 1 } }}>
      <TableHead><TableRow>{head.map((h) => <TableCell key={h}>{h}</TableCell>)}</TableRow></TableHead>
      <TableBody>{children}</TableBody>
    </Table>
  )
}

const target = (config, id) => config.targets.find((t) => t.id === id)
const label = (t, group, id) => t(`${group}.${id}`, { defaultValue: id })

function Streams({ rows, config, t }) {
  const roles = config.methods.aedseo.stream_roles
  const options = config.filters.location?.options ?? []
  const where = (value) => configLabel(t, options.find((o) => o.value === value)?.label_key, value)
  // Named as on the tab, so a reader finds the chart behind each stream.
  const panel = (tgt, ref) => {
    const found = tgt?.pages.find((p) => p.id === ref.page)?.panels.find((q) => q.id === ref.panel)
    return found ? panelLabel(t, found) : ref.panel
  }
  return (
    <Grid head={[t('methodology.columns.pathogen'), t('methodology.columns.location'), ...roles.map((r) => t(`role.${r}`))]}>
      {rows.map((r) => {
        const tgt = target(config, r.target)
        return (
          <TableRow key={`${r.target}/${r.location}`}>
            <TableCell>{configLabel(t, tgt?.label_key, r.target)}</TableCell>
            <TableCell>{where(r.location)}</TableCell>
            {roles.map((role) => (
              <TableCell key={role}>
                {r.streams ? panel(tgt, r.streams[role]) : <i>{t('methodology.notConfigured')}</i>}
              </TableCell>
            ))}
          </TableRow>
        )
      })}
    </Grid>
  )
}

function IndicatorModels({ rules, t, lang }) {
  const per = (n) => new Intl.NumberFormat(lang).format(n)
  const describe = (r) => {
    if (r.kind === 'count') {
      return [t('methodology.models.count', { units: r.units.map((u) => label(t, 'unit', u)).join(', ') }),
              t('methodology.models.asCounts')]
    }
    if (r.kind === 'rate') {
      const name = label(t, 'indicators', r.indicator)
      return [r.unit ? `${name} (${label(t, 'unit', r.unit)})` : name,
              t('methodology.models.asRate', { denominator: inSentence(label(t, 'indicators', r.denominator)), per: per(r.per) })]
    }
    return [t('methodology.models.other'), t('methodology.models.constant')]
  }
  return (
    <Grid head={[t('methodology.columns.indicator'), t('methodology.columns.modelled')]}>
      {rules.map((r) => {
        const [what, how] = describe(r)
        return <TableRow key={JSON.stringify(r)}><TableCell>{what}</TableCell><TableCell>{how}</TableCell></TableRow>
      })}
    </Grid>
  )
}

function PhasePatterns({ rows, config, t }) {
  return (
    <Grid head={[t('methodology.columns.pathogen'), t('methodology.columns.gradedAs')]}>
      {rows.map((r) => (
        <TableRow key={r.target}>
          <TableCell>{configLabel(t, target(config, r.target)?.label_key, r.target)}</TableCell>
          <TableCell>{t(`methodology.pattern.${r.pattern}`)}</TableCell>
        </TableRow>
      ))}
    </Grid>
  )
}

function Censored({ rows, t }) {
  return (
    <Grid head={[t('methodology.columns.feed'), t('methodology.columns.values')]}>
      {rows.map((r) => (
        <TableRow key={r.feed}>
          <TableCell>{label(t, 'feeds', r.feed)}</TableCell>
          <TableCell>{r.qualities.map((q) => label(t, 'quality', q)).join(', ')}</TableCell>
        </TableRow>
      ))}
    </Grid>
  )
}

function Levels({ method, config, t }) {
  const levels = config.methods[method].levels
  return (
    <Grid head={[t('methodology.columns.level'), t('methodology.columns.colour')]}>
      {levels.map((level) => {
        const tone = levelTone(levels, level)
        return (
          <TableRow key={level} data-tone={tone}>
            <TableCell>{t(`level.${level}`)}</TableCell>
            <TableCell>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}><ToneDot tone={tone} />{t(`methodology.tone.${tone}`)}</Box>
            </TableCell>
          </TableRow>
        )
      })}
    </Grid>
  )
}

export function Block({ name, blocks }) {
  const { t, i18n } = useTranslation()
  const config = useQuery({ queryKey: ['config'], queryFn: fetchConfig }).data
  const data = blocks?.[name]
  let body = null
  if (config && data) {
    body = name === 'streams' ? <Streams rows={data} config={config} t={t} />
      : name === 'indicator_models' ? <IndicatorModels rules={data} t={t} lang={i18n.language} />
        : name === 'phase_patterns' ? <PhasePatterns rows={data} config={config} t={t} />
          : name === 'censored' ? <Censored rows={data} t={t} />
            : name === 'levels' ? <Levels method={data.method} config={config} t={t} /> : null
  }
  return <GeneratedBox caption={t(`methodology.caption.${name}`, { defaultValue: name })}>{body}</GeneratedBox>
}
