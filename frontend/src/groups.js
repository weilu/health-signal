import { configLabel } from './labels.js'

// Panels (or summary rows) grouped as the overview groups them: by source feed, then pathogen-specific vs
// syndromic, then the tabs a series is shared across. Groups keep their first appearance and their panels'
// order; a panel without a group (phase, summary) stays where it is, alone and unheaded.
//
// A heading names only what tells groups apart: the source where the panels mix sources (or always, for the
// summary, which spans them), the kind where a source has both. Headings appear only when there are groups
// to tell apart, unless `alwaysSource` asks for them.
export function groupPanels(t, items, { panelOf = (item) => item, alwaysSource = false } = {}) {
  const groups = []
  const byKey = new Map()
  const kinds = new Map()
  for (const item of items) {
    const p = panelOf(item)
    // A queried panel the server didn't group still belongs to its feed.
    const g = p.group ?? (p.query && { feed: p.query.feed, targets: [] })
    if (!g) {
      groups.push({ key: `panel:${p.id}`, items: [item] })
      continue
    }
    kinds.set(g.feed, (kinds.get(g.feed) ?? new Set()).add(g.kind))
    const key = `${g.feed}.${g.kind}.${g.targets.join('/')}`
    if (!byKey.has(key)) {
      const group = { key, items: [], group: g }
      byKey.set(key, group)
      groups.push(group)
    }
    byKey.get(key).items.push(item)
  }
  const mixed = kinds.size > 1
  const headed = alwaysSource || byKey.size > 1
  for (const group of byKey.values()) {
    if (!headed) continue
    const { feed, kind, targets } = group.group
    const source = (alwaysSource || mixed) && t(`feeds.${feed}`, { defaultValue: feed })
    const kindLabel = kinds.get(feed).size > 1 && t(`summary.group.${kind}`)
    const shared = targets.length > 1
      && t('summary.sharedAcross', { targets: targets.map((id) => configLabel(t, `targets.${id}`, id)).join(' / ') })
    group.heading = { source: source || (kindLabel ? undefined : t(`feeds.${feed}`, { defaultValue: feed })), kind: kindLabel, shared }
  }
  return groups.map(({ group, ...rest }) => rest)
}
