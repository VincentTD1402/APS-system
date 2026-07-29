import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    // Vite rejects any Host header not listed here. The gateway forwards requests
    // still carrying the public hostname, so it must be allowed explicitly.
    allowedHosts: ['aps-fe.gsystem.ai'],
    // The TLS gateway in front of this server does not proxy websocket upgrades,
    // so HMR can never connect. Disabling it stops the server side; the injected
    // client still retries once and logs a connection error, which is harmless.
    hmr: false,
  },
})
