import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The SPA always calls the API under a relative `/api` base. In dev, Vite proxies
// that to the FastAPI backend (stripping `/api`, since the backend mounts routers at
// the root). In production the same `/api` path is handled by Caddy (`handle_path
// /api/*` -> quanta-backend), so no absolute origin is ever hard-coded.
const API_TARGET = process.env.VITE_API_TARGET || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: API_TARGET,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
