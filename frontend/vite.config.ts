import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// In development the API runs on port 8000 (`uv run trademind serve`).
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    css: false,
  },
});
