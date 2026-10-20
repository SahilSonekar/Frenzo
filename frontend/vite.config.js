import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// ---------------------------------------------------------------------------
// Vite configuration
//
// Environment variables
// ---------------------
// Create a frontend/.env file (gitignored) for local overrides:
//   VITE_API_URL=http://localhost:8000
//
// In production set VITE_API_URL to the public backend URL before building:
//   VITE_API_URL=https://api.yoursite.com npm run build
//
// Vite automatically exposes any VITE_* variable to the browser bundle via
// import.meta.env.VITE_*  — no extra `define` configuration is needed.
// ---------------------------------------------------------------------------

export default defineConfig({
  plugins: [vue()],

  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },

  server: {
    // Development server — accessible from Docker / LAN.
    host: '0.0.0.0',
    port: 5173,
    hmr: {
      port: 5173,
    },
  },
})
