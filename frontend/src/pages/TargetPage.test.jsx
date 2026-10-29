// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import TargetPage from './TargetPage.jsx'

// The panels themselves are tested on their own; here only where the page puts them.
vi.mock('../charts/TimeSeriesPanel.jsx', () => ({ TimeSeriesPanel: ({ panel }) => <p>{`panel:${panel.id}`}</p> }))
vi.mock('../charts/PhasePanel.jsx', () => ({ PhasePanel: () => null }))
vi.mock('../charts/SummaryPanel.jsx', () => ({ SummaryPanel: () => null }))
afterEach(cleanup)

const panel = (id, kind, targets = ['Influenza']) => ({ id, type: 'timeseries', query: { feed: 'clinical' },
                                                        group: { feed: 'clinical', kind, targets } })

it("nests a page's charts under their group's heading, in the summary's order", () => {
  render(<TargetPage target={{ id: 'Influenza' }} page={{ id: 'clinical', panels: [
    panel('adm', 'pathogen_specific'), panel('ili', 'syndromic', ['SARS-CoV-2', 'Influenza']), panel('icu', 'pathogen_specific')] }} />)
  const order = screen.getAllByText(/^(panel:|summary\.group\.)/).map((x) => x.textContent)
  expect(order).toEqual(['summary.group.pathogen_specific', 'panel:adm', 'panel:icu', 'summary.group.syndromic', 'panel:ili'])
  expect(screen.getByRole('heading', { name: /summary\.group\.syndromic/ })).toBeTruthy()
})

it('adds no heading when a page has one group', () => {
  render(<TargetPage target={{ id: 'Influenza' }} page={{ id: 'clinical', panels: [panel('adm', 'pathogen_specific')] }} />)
  expect(screen.queryByRole('heading')).toBeNull()
})
