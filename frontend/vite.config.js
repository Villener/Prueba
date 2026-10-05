import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Una marca por compilacion. Va DENTRO del codigo (__VERSION_APP__) y en
// /version.json; si no coinciden, el celular tiene abierta una version vieja y
// la app ofrece actualizar (src/core/pwa.js, vigilarVersion).
const VERSION = new Date().toISOString()

function versionApp() {
  const json = JSON.stringify({ version: VERSION })
  return {
    name: 'bajagas-version',
    generateBundle() {
      this.emitFile({ type: 'asset', fileName: 'version.json', source: json })
    },
    configureServer(server) {
      server.middlewares.use('/version.json', (req, res) => {
        res.setHeader('Content-Type', 'application/json')
        res.end(json)
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), versionApp()],
  define: { __VERSION_APP__: JSON.stringify(VERSION) },
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } },
  },
})
