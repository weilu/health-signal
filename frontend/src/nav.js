import { matchPath } from 'react-router-dom'

// Matches like the routes (case-insensitive, optional trailing slash) so the tabs agree with what renders.
// Any page of a target activates that target's tab.
export function activePage(targets, pathname) {
  for (const target of targets) {
    const page = target.pages.find((p) => matchPath(p.path, pathname))
    if (page) return { target, page }
  }
  return null
}
