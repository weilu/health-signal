import 'katex/dist/katex.min.css'
import { Children, isValidElement, useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Box, Link, Paper, Typography } from '@mui/material'
import { alpha } from '@mui/material/styles'
import { useTranslation } from 'react-i18next'
import ReactMarkdown from 'react-markdown'
import rehypeKatex from 'rehype-katex'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import { fetchMethodology } from '../api.js'
import { Block } from '../methodology/blocks.jsx'
import { ResourceBoundary } from '../ResourceBoundary.jsx'

// Unicode-aware, so Greek headings get anchors too.
export const slug = (text) => text.toLowerCase().trim().replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-|-$/g, '')

const textOf = (children) => Children.toArray(children)
  .map((c) => (typeof c === 'string' ? c : isValidElement(c) ? textOf(c.props.children) : '')).join('')

// The contents list reads the Markdown's own ## and ### headings, skipping any inside a fenced block.
function headings(markdown) {
  let fenced = false
  return markdown.split('\n').flatMap((line) => {
    if (line.startsWith('```')) fenced = !fenced
    const match = !fenced && line.match(/^(##|###)\s+(.+)$/)
    return match ? [{ level: match[1].length, text: match[2].replace(/[*_`]/g, '') }] : []
  })
}

function Setting({ value }) {
  const { t } = useTranslation()
  const text = value.startsWith('t:') ? t(value.slice(2)) : value
  return (
    <Box component="span" data-setting sx={(theme) => ({ px: 0.25, bgcolor: alpha(theme.palette.warning.main, 0.1),
                                                         borderBottom: '1px dotted', borderColor: 'warning.main' })}>
      {text}
    </Box>
  )
}

function Heading({ as, children }) {
  return <Typography variant={as === 'h2' ? 'h5' : 'h6'} component={as} id={slug(textOf(children))}
    sx={{ mt: 4, mb: 1, scrollMarginTop: 16 }}>{children}</Typography>
}

function Article({ page }) {
  const components = {
    h2: ({ children }) => <Heading as="h2">{children}</Heading>,
    h3: ({ children }) => <Heading as="h3">{children}</Heading>,
    // Settings arrive as inline code `hs:<value>`; anything else stays code.
    code: ({ className, children }) => {
      const text = textOf(children)
      return !className && text.startsWith('hs:') ? <Setting value={text.slice(3)} /> : <code className={className}>{children}</code>
    },
    // A generated block arrives as a fenced `hs-block` naming it.
    pre: ({ children }) => {
      const code = Children.only(children)
      return code.props.className === 'language-hs-block'
        ? <Block name={textOf(code.props.children).trim()} blocks={page.blocks} />
        : <pre>{children}</pre>
    },
  }
  return (
    <Box sx={{ '& table': { borderCollapse: 'collapse', my: 2 }, '& th, & td': { textAlign: 'left', px: 1, py: 0.5,
                                                                                   borderBottom: 1, borderColor: 'divider' } }}>
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]} components={components}>
        {page.markdown}
      </ReactMarkdown>
    </Box>
  )
}

function Contents({ items }) {
  const { t } = useTranslation()
  const [current, setCurrent] = useState(null)
  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') return undefined
    const observer = new IntersectionObserver((entries) => {
      const seen = entries.filter((e) => e.isIntersecting).map((e) => e.target.id)
      if (seen.length) setCurrent(seen[0])
    }, { rootMargin: '0px 0px -70% 0px' })
    items.forEach((h) => { const el = document.getElementById(slug(h.text)); if (el) observer.observe(el) })
    return () => observer.disconnect()
  }, [items])
  return (
    <Box component="nav" aria-label={t('methodology.contents')}
      sx={{ position: { md: 'sticky' }, top: 16, alignSelf: 'start', pr: 2, borderRight: { md: 1 }, borderColor: 'divider' }}>
      {items.map((h) => (
        <Link key={slug(h.text)} href={`#${slug(h.text)}`} underline="hover"
          aria-current={current === slug(h.text) ? 'location' : undefined}
          sx={{ display: 'block', pl: h.level === 3 ? 2 : 0, py: 0.5, fontSize: '0.875rem',
                color: current === slug(h.text) ? 'text.primary' : 'text.secondary',
                fontWeight: current === slug(h.text) ? 600 : 400 }}>
          {h.text}
        </Link>
      ))}
    </Box>
  )
}

export default function MethodologyPage() {
  const { t, i18n } = useTranslation()
  const query = useQuery({ queryKey: ['methodology', i18n.language], queryFn: () => fetchMethodology(i18n.language) })
  return (
    <ResourceBoundary query={query}>
      {(page) => (
        <Paper variant="outlined" sx={{ p: { xs: 2, md: 3 } }}>
          <Typography variant="h4" component="h1" sx={{ mb: 2 }}>{t('nav.methodology')}</Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '220px minmax(0, 1fr)' }, gap: 4 }}>
            <Contents items={headings(page.markdown)} />
            <Article page={page} />
          </Box>
        </Paper>
      )}
    </ResourceBoundary>
  )
}
