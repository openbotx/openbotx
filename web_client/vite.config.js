import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  base: '/app/',
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/public': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true }
    }
  },
  build: {
    outDir: '../openbotx/web_client',
    emptyOutDir: true,
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks: {
          'md-editor': ['md-editor-v3'],
          'primevue': ['primevue'],
        }
      }
    }
  }
})
