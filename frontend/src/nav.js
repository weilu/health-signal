// The configured page the URL is on, with its target — drives both tab rows. Pages are routed by exact
// path, so an exact match is enough; any page of a target activates that target's tab.
export function activePage(targets, pathname) {
  for (const target of targets) {
    const page = target.pages.find((p) => p.path === pathname)
    if (page) return { target, page }
  }
  return null
}
