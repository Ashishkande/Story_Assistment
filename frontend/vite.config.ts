import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],

  server: {
    port: 3000,

    proxy: {
      "/api": {
        target: "http://3.110.55.88:8000",
        changeOrigin: true,
      },

      "/health": {
        target: "http://3.110.55.88:8000",
        changeOrigin: true,
      },
    },
  },
});