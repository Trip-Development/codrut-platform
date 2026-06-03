import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        burgundy: {
          DEFAULT: "#8B0000",
          50: "#FDF6F6",
          100: "#FBE9E9",
          200: "#F5C9C9",
          400: "#B83333",
          500: "#8B0000",
          600: "#7A0000",
          700: "#6A0000",
          800: "#5A0000",
          900: "#4A0000",
        },
        cream: {
          DEFAULT: "#FAF6EE",
          50: "#FDFBF6",
          100: "#FAF6EE",
          200: "#F2EAD8",
        },
        ochre: {
          DEFAULT: "#B8860B",
          100: "#FBF1D7",
          500: "#B8860B",
          700: "#8E6708",
        },
        charcoal: {
          DEFAULT: "#1C1A1A",
          800: "#2A2826",
        },
        background: "var(--background)",
        foreground: "var(--foreground)",
        surface: "var(--surface)",
        "surface-muted": "var(--surface-muted)",
        codrut: {
          burgundy: "#8B0000",
          cream: "#FAF6EE",
          ink: "#191716",
          ochre: "#c28f2c",
        },
      },
      fontFamily: {
        sans: ["Inter Tight", "Inter", "system-ui", "sans-serif"],
        display: ["Fraunces", "Georgia", "serif"],
      },
      transitionTimingFunction: {
        spring: "cubic-bezier(0.34, 1.56, 0.64, 1)",
        "spring-soft": "cubic-bezier(0.22, 1, 0.36, 1)",
      },
    },
  },
  plugins: [],
};

export default config;
