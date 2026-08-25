import { defineConfig } from "astro/config";
import bun from "@nurodev/astro-bun";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  output: "server",
  adapter: bun(),
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
