import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Local dev proxy: when VITE_API_URL is not set (empty string),
    // all /query, /upload, /health, etc. calls get proxied to the local FastAPI server.
    proxy: {
      '/query': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/upload': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/health': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/documents': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/quiz': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/flashcards': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
