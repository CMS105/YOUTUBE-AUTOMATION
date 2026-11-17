/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#080c14",
        surface: "#0f172a",
        "surface-elevated": "#1e293b",
        "surface-hover": "#26354a",
        border: "#1e293b",
        "border-light": "#334155",
        accent: {
          cyan: "#06b6d4",
          "cyan-bright": "#22d3ee",
          neon: "#00f0ff",
          pink: "#f43f5e",
          amber: "#f59e0b",
          emerald: "#10b981",
        },
        text: {
          primary: "#f8fafc",
          secondary: "#94a3b8",
          muted: "#64748b",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
    },
  },
  plugins: [],
};
