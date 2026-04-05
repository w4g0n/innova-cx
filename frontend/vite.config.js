import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: ['innovacx.net', 'www.innovacx.net', 'localhost', 'staff.innovacx.net'],
  },
  build: {
    sourcemap: false,   // never ship source maps to production
    minify: 'esbuild',  // explicit — esbuild is fast and already bundled with Vite
  },
})