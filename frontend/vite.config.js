import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: ['innovacx.net', 'www.innovacx.net', 'localhost', 'staff.innovacx.net'],
  },
  preview: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: ['innovacx.net', 'www.innovacx.net', 'localhost', 'staff.innovacx.net'],
  },
  build: {
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true,
        drop_debugger: true,
      }
    }
  }
})