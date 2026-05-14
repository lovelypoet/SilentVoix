import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const backendHost = process.env.VITE_BACKEND_HOST || 'localhost'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    host: '0.0.0.0',
    proxy: {
      '/ws': {
        target: `ws://${backendHost}:8000`,
        ws: true,
      },
      '/health': `http://${backendHost}:8000`,
      '/mock-payload': `http://${backendHost}:8000`,
      '/labels': `http://${backendHost}:8000`,
    },
  },
})
