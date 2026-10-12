import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

// DOJO_TARGET=reference forces the clean implementation; otherwise use workspace/ when it exists.
const target = process.env.DOJO_TARGET ?? (existsSync(resolve(__dirname, "workspace/src")) ? "workspace" : "reference");

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@app": resolve(__dirname, target, "src") } },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
  },
});
