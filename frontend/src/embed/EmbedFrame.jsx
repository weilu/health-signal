import { useEffect, useRef, useState } from 'react'
import { Box } from '@mui/material'
import { url } from '../base.js'

// The page reads what it needs from its address; a filter the dashboard doesn't have is left out.
export function embedSrc(embed, { lang, location, range }) {
  const params = new URLSearchParams({ lang })
  if (location) params.set('location', location)
  if (range) {
    params.set('from', range.from)
    params.set('to', range.to)
  }
  return `${url(`/embeds/${embed}`)}?${params}`
}

// Sized by the page itself, which posts {type: 'health-signal:height', height}, so the tab scrolls as one page
// rather than a frame inside it.
export function EmbedFrame({ src, title }) {
  const frame = useRef(null)
  const [height, setHeight] = useState(null)
  useEffect(() => {
    const onMessage = (e) => {
      if (e.source !== frame.current?.contentWindow || e.data?.type !== 'health-signal:height') return
      if (Number.isFinite(e.data.height)) setHeight(e.data.height)
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [])
  return (
    <Box component="iframe" ref={frame} src={src} title={title}
      sx={{ display: 'block', width: '100%', border: 0 }} style={{ height: height ? `${height}px` : '80vh' }} />
  )
}
