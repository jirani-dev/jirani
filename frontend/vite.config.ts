/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',      // makes it accessible on the network
    port: 5173,
    // Same-origin semantics in dev (locked topology): /api and /static go
    // through nginx (:80) so X-Accel-Redirect media works and no CORS
    // surface exists. Override VITE_API_BASE for the container-less flow.
    proxy: {
      '/api': { target: 'http://localhost:80' },
      '/static': { target: 'http://localhost:80' },
    },
  },
  preview: {
    host: '0.0.0.0',      // same for production preview
    port: 4173,
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/setupTests.ts'],
    css: false,
  },
})
