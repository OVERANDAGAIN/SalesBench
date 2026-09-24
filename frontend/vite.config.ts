import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: { '/api/health': { target: 'http://127.0.0.1:8000', rewrite: () => '/health' }, '/api/v1': { target: 'http://127.0.0.1:8000' } },
  },
  preview: { host: '127.0.0.1', port: 4173, strictPort: true, proxy: { '/api/v1': { target: 'http://127.0.0.1:8000' } } },
  test: { include: ['tests/**/*.test.ts'], environment: 'node' },
})
