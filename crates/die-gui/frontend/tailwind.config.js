/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // DIE dark theme tokens (CSS variables in index.css)
        window: "rgb(var(--bg-window))",
        panel: "rgb(var(--bg-panel))",
        input: "rgb(var(--bg-input))",
        hover: "rgb(var(--bg-hover))",
        selected: "rgb(var(--bg-selected))",
        accent: "rgb(var(--bg-accent))",
        "fg-primary": "rgb(var(--fg-primary))",
        "fg-secondary": "rgb(var(--fg-secondary))",
        "fg-muted": "rgb(var(--fg-muted))",
        "border-c": "rgb(var(--border-color))",
        "border-l": "rgb(var(--border-light))",
        "accent-blue": "rgb(var(--accent-blue))",
        "accent-green": "rgb(var(--accent-green))",
        "accent-red": "rgb(var(--accent-red))",
        "accent-yellow": "rgb(var(--accent-yellow))",
        "accent-purple": "rgb(var(--accent-purple))",
      },
    },
  },
  plugins: [],
};
