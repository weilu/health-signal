import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: './',  // relative asset paths so the SPA loads under a URL prefix (e.g. Posit Connect)
  build: { outDir: '../src/health_signal/_ui', emptyOutDir: true },
  // `npm run dev` serves the SPA; proxy the API/auth routes to the FastAPI backend (uvicorn on :8000)
  // so dev talks to a real server. Prod serves the built SPA from FastAPI, so no proxy is needed.
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/login': 'http://127.0.0.1:8000',
      '/logout': 'http://127.0.0.1:8000',
    },
  },
})
