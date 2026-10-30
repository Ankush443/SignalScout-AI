import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dashboard dev server (5173) and preview server (4173) are allowed by
// the backend CORS defaults in src/config.py.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: false,
  },
  preview: {
    port: 4173,
    strictPort: false,
  },
});
