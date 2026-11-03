// Under a proxy mount (Posit Connect's /content/<guid>/) the server injects <base href>; root-absolute paths would
// skip it and reach the host's own routes.
export const basePath = () => (document.querySelector('base')?.getAttribute('href') ?? '/').replace(/\/$/, '')

export const url = (path) => basePath() + path
