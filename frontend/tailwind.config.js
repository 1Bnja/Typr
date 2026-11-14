/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: 'rgb(from var(--canvas) r g b / <alpha-value>)',
        surface: 'var(--surface)',
        muted: 'var(--muted)',
        subtle: 'var(--hover)',
        divider: 'rgb(from var(--line) r g b / <alpha-value>)',
        accent: 'var(--accent)',
        danger: 'var(--danger-ink)',
        mint: '#2fd9b4',
        charcoal: 'rgb(from var(--ink) r g b / <alpha-value>)',
        amber: '#f2c21a',
        red: '#e8453c',
        blue: '#7ea8f5',
        },
      },
  },
  plugins: [],
}

