import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://backend:8080',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      },
      '/ws': {
        target: 'http://backend:8080',
        ws: true,
        changeOrigin: true,
        secure: false
      },
      '/auth': {  // 👈 thêm route /auth
        target: 'http://backend:8080',
        changeOrigin: true,
      },
      '/static/tts': {
        target: 'http://backend:8080',
        changeOrigin: true,
      },
      '/pics': {
        target: 'http://backend:8080',
        changeOrigin: true,
      },
    }
  },
})
