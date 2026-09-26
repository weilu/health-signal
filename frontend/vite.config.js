import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: './',  // relative asset paths so the SPA loads under a URL prefix (e.g. Posit Connect)
  build: { outDir: '../src/health_signal/_ui', emptyOutDir: true },
})
