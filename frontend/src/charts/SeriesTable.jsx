import { Table, TableBody, TableCell, TableContainer, TableHead, TableRow } from '@mui/material'
import { useTranslation } from 'react-i18next'

export function SeriesTable({ periods, series, unit }) {
  const { t, i18n } = useTranslation()
  const fmt = new Intl.NumberFormat(i18n.resolvedLanguage, { maximumFractionDigits: 2 })
  const rows = periods.map((p, i) => ({ p, i })).reverse()  // newest week first
  return (
    <TableContainer sx={{ maxHeight: 320 }}>
      <Table size="small" stickyHeader>
        <caption>{unit}</caption>
        <TableHead>
          <TableRow>
            <TableCell>{t('chart.period')}</TableCell>
            {series.map((s) => <TableCell key={s.key} align="right">{s.label}</TableCell>)}
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map(({ p, i }) => (
            <TableRow key={p}>
              <TableCell component="th" scope="row">{p}</TableCell>
              {series.map((s) => (
                <TableCell key={s.key} align="right" sx={{ fontVariantNumeric: 'tabular-nums' }}>
                  {s.qualities?.[i] ? t(`quality.${s.qualities[i]}`, { defaultValue: s.qualities[i] })
                    : s.values[i] == null ? '—' : fmt.format(s.values[i])}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  )
}
