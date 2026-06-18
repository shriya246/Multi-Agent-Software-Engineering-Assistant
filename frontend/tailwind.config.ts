import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        panel: "#0b1220",
        panelSoft: "#121c2f",
        line: "#22304a",
        ink: "#e5eefc",
        muted: "#8ca0bf",
        accent: "#7dd3fc",
        accentStrong: "#38bdf8"
      },
      boxShadow: {
        soft: "0 24px 60px rgba(0, 0, 0, 0.24)"
      }
    }
  },
  plugins: []
} satisfies Config;
