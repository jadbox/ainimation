import { defineConfig } from "astro/config";
import node from "@astrojs/node";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  output: "server",
  adapter: node({ mode: "standalone" }),
  server: {
    port: 8080,
  },
  vite: {
    plugins: [tailwindcss()],
    server: {
      allowedHosts: ["dev.jonathandunlap.com"],
    },
  },
});
