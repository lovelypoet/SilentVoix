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
  /*
   * onnxruntime-web must not be pre-bundled. Its wasm build locates
   * `ort-wasm-simd-threaded.wasm` relative to `import.meta.url`, and esbuild
   * rewrites that to node_modules/.vite/deps/ without copying the binary
   * along. The dev server then answers that path with index.html, and ORT
   * fails compiling HTML as wasm ("failed to match magic number"). Excluding
   * it leaves the module served from its own directory, where the .wasm
   * actually sits. `vite build` was never affected, so this is dev-only.
   */
  optimizeDeps: {
    exclude: ['onnxruntime-web', 'onnxruntime-web/wasm'],
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
