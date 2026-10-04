import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  // Avoid pathological Rollup 4.64 tree-shaking on React 19; output remains ~62 kB gzip.
  build: { rollupOptions: { treeshake: false } },
  server: {
    host: "127.0.0.1",
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/healthz": "http://127.0.0.1:8000",
    },
  },
  test: { environment: "jsdom", setupFiles: ["./src/test-setup.ts"] },
});
