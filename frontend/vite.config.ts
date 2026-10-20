import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  // The browser calls relative /api routes; Vite forwards those from the server.
  // Override this for a backend running somewhere other than the local dev host.
  const backendTarget = env.VITE_DEV_PROXY_TARGET || env.BACKEND_API_URL || 'http://127.0.0.1:7860';

  return {
    plugins: [react()],
    server: {
      port: 3000,
      host: '0.0.0.0',
      allowedHosts: ['.e2b.app', '.e2b.dev'],
      proxy: {
        '/api': { target: backendTarget, changeOrigin: true },
        '/gradio': { target: backendTarget, changeOrigin: true, ws: true },
      },
    },
    build: {
      outDir: 'dist',
      emptyOutDir: true,
    },
  };
});
