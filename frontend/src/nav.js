// Pages are routed by exact path; any page of a target activates that target's tab.
export function activePage(targets, pathname) {
  for (const target of targets) {
    const page = target.pages.find((p) => p.path === pathname)
    if (page) return { target, page }
  }
  return null
}
