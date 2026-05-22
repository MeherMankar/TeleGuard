import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"
import { TanStackRouterVite } from "@tanstack/router-plugin/vite"
import tsconfigPaths from "vite-tsconfig-paths"

export default defineConfig({
  base: "/",
  plugins: [
    // TanStack Router file-based routing (must come before react plugin)
    TanStackRouterVite({ target: "react", autoCodeSplitting: true }),
    react(),
    tailwindcss(),
    tsconfigPaths(),
  ],
  build: {
    outDir: "dist",
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ["react", "react-dom"],
          router: ["@tanstack/react-router", "@tanstack/react-query"],
          ui: ["lucide-react", "sonner", "date-fns"],
        },
      },
    },
  },
  server: {
    port: 5173,
    // Proxy API calls to backend during local dev
    proxy: {
      "/api": {
        target: process.env.VITE_API_URL ?? "http://localhost:8080",
        changeOrigin: true,
      },
      "/ws": {
        target: process.env.VITE_WS_URL ?? "ws://localhost:8080",
        ws: true,
        changeOrigin: true,
      },
    },
  },
})
