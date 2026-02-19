import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
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
    }
  },
  build: {
    rollupOptions: {
      external: ['@mediapipe/tasks-vision'],
    },
  },
})
