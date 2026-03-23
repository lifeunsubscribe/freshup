import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { existsSync } from 'fs'

/**
 * Detects if the application is running inside a Docker container.
 *
 * Docker creates a .dockerenv file at the root of the filesystem.
 * We also support an explicit DOCKER_CONTAINER env var for flexibility.
 *
 * @returns {boolean} true if running in Docker, false otherwise
 */
function isRunningInDocker(): boolean {
  return existsSync('/.dockerenv') || process.env.DOCKER_CONTAINER === 'true'
}

/**
 * Security: Bind to localhost by default, 0.0.0.0 only in Docker.
 *
 * Binding to 0.0.0.0 exposes the dev server on ALL network interfaces,
 * which is a security risk when running locally (accessible on LAN/WiFi).
 *
 * - Docker: Requires 0.0.0.0 for host-to-container networking
 * - Local dev: Use 127.0.0.1 (localhost only) to minimize attack surface
 *
 * Following OWASP principle: Minimize attack surface by default.
 */
const devServerHost = isRunningInDocker() ? '0.0.0.0' : '127.0.0.1'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: devServerHost,
    port: 5173,
    // Fail if port is already in use (prevents silent port changes)
    strictPort: true,
    watch: {
      // Use polling for file watching (required for Docker volume mounts on some systems)
      usePolling: true,
    },
  },
})
