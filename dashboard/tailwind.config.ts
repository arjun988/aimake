import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#E8F1FD",
          100: "#D1E4FB",
          200: "#A3C9F7",
          500: "#3B8FF0",
          600: "#1A73E8",
          700: "#1558B8",
          800: "#0F3F86",
          900: "#0B1220",
        },
        surface: {
          DEFAULT: "var(--surface)",
          raised: "var(--surface-raised)",
          muted: "var(--surface-muted)",
          border: "var(--border)",
          "border-strong": "var(--border-strong)",
        },
        ink: {
          DEFAULT: "var(--ink)",
          secondary: "var(--ink-secondary)",
          muted: "var(--ink-muted)",
          inverse: "var(--ink-inverse)",
        },
        nav: {
          DEFAULT: "var(--nav)",
          muted: "var(--nav-muted)",
          border: "var(--nav-border)",
          hover: "var(--nav-hover)",
          active: "var(--nav-active)",
        },
        success: {
          DEFAULT: "var(--success)",
          soft: "var(--success-soft)",
        },
        warning: {
          DEFAULT: "var(--warning)",
          soft: "var(--warning-soft)",
        },
        danger: {
          DEFAULT: "var(--danger)",
          soft: "var(--danger-soft)",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(11, 18, 32, 0.04)",
        "card-hover": "0 4px 16px rgba(11, 18, 32, 0.06)",
        pop: "0 12px 28px rgba(11, 18, 32, 0.12)",
      },
      borderRadius: {
        lg: "8px",
        xl: "10px",
        "2xl": "14px",
      },
      animation: {
        "fade-in": "fadeIn 0.25s ease-out forwards",
        "slide-up": "slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
