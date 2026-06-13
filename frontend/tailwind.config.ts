import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ['selector', '[data-theme="dark"]'],
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        burgundy: {
          DEFAULT: "var(--burgundy)",
          50: "#FDF6F6",
          100: "#FBE9E9",
          200: "#F5C9C9",
          400: "#B83333",
          500: "var(--burgundy)",
          600: "#780404",
          700: "#650303",
          800: "#520303",
          900: "#3F0202",
        },
        cream: {
          DEFAULT: "#FAF6EE",
          50: "#FDFBF6",
          100: "#FAF6EE",
          200: "#F2EAD8",
        },
        ochre: {
          DEFAULT: "var(--ochre)",
          100: "#FBF1D7",
          500: "var(--ochre)",
          700: "#8E6708",
        },
        charcoal: {
          DEFAULT: "#5E5E5E",
          800: "#2A2826",
        },
        background: "var(--background)",
        foreground: "var(--foreground)",
        surface: "var(--surface)",
        "surface-muted": "var(--surface-muted)",
        success: {
          DEFAULT: "var(--success)",
          ink: "var(--success-ink)",
        },
        codrut: {
          burgundy: "#890505",
          green: "#A3D376",
          gray: "#5E5E5E",
          cream: "#FAF6EE",
          ink: "#191716",
          ochre: "#c28f2c",
        },
      },
      boxShadow: {
        'glass': '0 8px 32px 0 rgba(0, 0, 0, 0.04)',
        'glass-hover': '0 12px 48px 0 rgba(0, 0, 0, 0.08), 0 0 0 1px rgba(255, 255, 255, 0.4) inset',
        'premium': '0 4px 24px -4px rgba(137, 5, 5, 0.06), 0 12px 32px -8px rgba(0, 0, 0, 0.04)',
        'premium-hover': '0 8px 32px -4px rgba(137, 5, 5, 0.12), 0 16px 48px -12px rgba(0, 0, 0, 0.08), 0 0 0 1px rgba(255,255,255,0.6) inset',
        'inner-light': 'inset 0 1px 0 0 rgba(255, 255, 255, 0.6)',
      },
      fontFamily: {
        sans: ["Inter Tight", "Inter", "system-ui", "sans-serif"],
        display: ["Fraunces", "Georgia", "serif"],
      },
      transitionTimingFunction: {
        spring: "cubic-bezier(0.34, 1.56, 0.64, 1)",
        "spring-soft": "cubic-bezier(0.22, 1, 0.36, 1)",
        "spring-bouncy": "cubic-bezier(0.68, -0.6, 0.32, 1.6)",
      },
      keyframes: {
        'fade-in-up': {
          '0%': { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'float': {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        'pulse-glow': {
          '0%, 100%': { opacity: '0.4', transform: 'scale(1)' },
          '50%': { opacity: '0.8', transform: 'scale(1.05)' },
        }
      },
      animation: {
        'fade-in-up': 'fade-in-up 0.6s cubic-bezier(0.22, 1, 0.36, 1) forwards',
        'float': 'float 6s ease-in-out infinite',
        'pulse-glow': 'pulse-glow 4s ease-in-out infinite',
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'hero-mesh': 'radial-gradient(at 10% 0%, rgba(137, 5, 5, 0.04) 0px, transparent 50%), radial-gradient(at 90% 10%, rgba(194, 143, 44, 0.04) 0px, transparent 50%), radial-gradient(at 50% 100%, rgba(163, 211, 118, 0.03) 0px, transparent 50%)',
      }
    },
  },
  plugins: [],
};

export default config;
