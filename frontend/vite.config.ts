import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// The SPA always calls the API under a relative `/api` base. In dev, Vite proxies that to
// the FastAPI backend (stripping `/api`, since the backend mounts routers at the root); in
// production Caddy does the same, so no absolute origin is ever hard-coded.
//
// - The backend origin defaults to :8000 but can be overridden with VITE_API_TARGET (e.g.
//   in .env.local) when :8000 is already taken on the host.
// - The dev-server port honors $PORT so the preview harness can assign one (autoPort).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiTarget =
    process.env.VITE_API_TARGET || env.VITE_API_TARGET || "http://localhost:8000";
  const port = Number(process.env.PORT || env.PORT) || 5173;
  return {
    plugins: [react()],
    server: {
      port,
      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ""),
        },
      },
    },
  };
});
