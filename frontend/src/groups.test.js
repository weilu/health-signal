import { describe, expect, it } from 'vitest'
import { groupPanels } from './groups.js'

const t = (key, options) => (options?.targets ? `${key}(${options.targets})` : options?.defaultValue ?? key)
const panel = (id, feed, kind, targets = ['Influenza']) => ({ id, type: 'timeseries', query: { feed }, group: { feed, kind, targets } })
const heads = (groups) => groups.map((g) => g.heading && [g.heading.source, g.heading.kind, g.heading.shared].filter(Boolean))

describe('groupPanels', () => {
  it('groups by kind in order of first appearance, keeping each panel order', () => {
    const groups = groupPanels(t, [panel('adm', 'clinical', 'pathogen_specific'), panel('ili', 'clinical', 'syndromic'),
                                   panel('icu', 'clinical', 'pathogen_specific')])
    expect(groups.map((g) => g.items.map((p) => p.id))).toEqual([['adm', 'icu'], ['ili']])
  })

  it("names the source only where the panels mix sources, and the kind only where a source has both", () => {
    const page = [panel('adm', 'clinical', 'pathogen_specific'), panel('ili', 'clinical', 'syndromic', ['SARS-CoV-2', 'Influenza'])]
    expect(heads(groupPanels(t, page))).toEqual([['summary.group.pathogen_specific'],
                                                 ['summary.group.syndromic', 'summary.sharedAcross(SARS-CoV-2 / Influenza)']])
    const mixed = [...page, panel('load', 'wastewater', 'pathogen_specific')]
    expect(heads(groupPanels(t, mixed))).toEqual([['clinical', 'summary.group.pathogen_specific'],
                                                  ['clinical', 'summary.group.syndromic', 'summary.sharedAcross(SARS-CoV-2 / Influenza)'],
                                                  ['wastewater']])
  })

  it('leaves ungrouped panels in place with no heading, and headings out when only one group remains', () => {
    const overview = [{ id: 'phase', type: 'phase' }, { id: 'summary', type: 'summary' }]
    expect(heads(groupPanels(t, overview))).toEqual([undefined, undefined])
    expect(heads(groupPanels(t, [panel('load', 'wastewater', 'pathogen_specific')]))).toEqual([undefined])
  })
})
