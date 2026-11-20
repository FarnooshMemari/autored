import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

const backend = process.env.AUTORED_BACKEND ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": backend,
      "/ws": { target: backend.replace(/^http/, "ws"), ws: true },
    },
  },
  test: { environment: "node" },
});
