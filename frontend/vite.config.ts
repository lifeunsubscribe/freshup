import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Bind to all interfaces for Docker container accessibility
    host: '0.0.0.0',
    port: 5173,
    // Fail if port is already in use (prevents silent port changes)
    strictPort: true,
    watch: {
      // Use polling for file watching (required for Docker volume mounts on some systems)
      usePolling: true,
    },
  },
})
