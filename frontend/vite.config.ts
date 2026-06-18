import react from "@vitejs/plugin-react";

export default {
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: true,
    css: true
  }
} as any;
