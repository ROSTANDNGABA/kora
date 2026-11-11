/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./templates/**/*.html", "./apps/**/templates/**/*.html", "./apps/**/*.py", "./static/js/**/*.js"],
  theme: {
    extend: {
      colors: {
        kora: {
          orange: { DEFAULT: "#F36F21", 50: "#FFF4EA", 100: "#FFE6D1", 200: "#FFCBA3", 300: "#FFAA6E", 400: "#FA8A41", 500: "#F36F21", 600: "#D95A12", 700: "#B3470F", 800: "#8C3911", 900: "#4A1F0E" },
          brown: { DEFAULT: "#4A1F0E", 700: "#5E2A16", 800: "#4A1F0E", 900: "#351509" },
          yellow: { DEFAULT: "#F5B800", 100: "#FFF3C4", 500: "#F5B800", 600: "#D69E00" },
          green: { DEFAULT: "#5B9E2D", 100: "#E4F2D8", 500: "#5B9E2D", 700: "#42761F" },
          cream: "#FFF4EA",
          verified: "#1D9BF0",
        },
      },
      fontFamily: {
        sans: ["Poppins", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
      },
      borderRadius: { xl: "0.875rem", "2xl": "1.25rem", "3xl": "1.75rem" },
      boxShadow: {
        soft: "0 2px 12px -2px rgba(74, 31, 14, 0.10)",
        card: "0 6px 24px -6px rgba(74, 31, 14, 0.15)",
        pop: "0 16px 40px -12px rgba(74, 31, 14, 0.28)",
      },
      keyframes: {
        "fade-up": { "0%": { opacity: 0, transform: "translateY(12px)" }, "100%": { opacity: 1, transform: "translateY(0)" } },
        shimmer: { "100%": { transform: "translateX(100%)" } },
      },
      animation: {
        "fade-up": "fade-up 0.35s ease-out both",
      },
    },
  },
  plugins: [require("@tailwindcss/forms")({ strategy: "class" })],
};
