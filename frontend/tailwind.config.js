/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          900: "#080c15",
          800: "#0d1424",
          700: "#131d33",
          600: "#1a2744",
        },
        accent: {
          blue: "#4f8ff7",
          cyan: "#22d3ee",
          red: "#f43f5e",
          amber: "#f59e0b",
          green: "#10b981",
        },
      },
      fontFamily: {
        sans: ['"DM Sans"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "monospace"],
      },
    },
  },
  plugins: [],
};