import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [
    react(),
  ],
  server: {
    port: 3000,
    host: '0.0.0.0',
    proxy: {
      '/api': 'http://127.0.0.1:7860',
      '/gradio': 'http://127.0.0.1:7860',
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
