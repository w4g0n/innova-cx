import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    watch: {
      usePolling: true,
      interval: 250,
    },
    allowedHosts: ['innovacx.net', 'www.innovacx.net', 'localhost', 'staff.innovacx.net'],
  },
  preview: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: ['innovacx.net', 'www.innovacx.net', 'localhost', 'staff.innovacx.net'],
  },
  build: {
    sourcemap: false, // ✅ security: no source exposure
    minify: 'terser', // ✅ better optimization than esbuild
    terserOptions: {
      compress: {
        drop_console: true, // ✅ removes console.log
        drop_debugger: true, // ✅ removes debugger
      }
    }
  }
})
