/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // 温暖的日记主题色
        diary: {
          50:  '#fdf8f0',
          100: '#f9edd8',
          200: '#f2d9b0',
          300: '#e8bf7e',
          400: '#dea04e',
          500: '#d48a33',
          600: '#c07028',
          700: '#9f5523',
          800: '#814522',
          900: '#6a3a1e',
        },
        ink: {
          50:  '#f6f5f3',
          100: '#e8e5df',
          200: '#d3cec4',
          300: '#b8b0a2',
          400: '#9c917f',
          500: '#887b68',
          600: '#756858',
          700: '#5f5549',
          800: '#514840',
          900: '#473f38',
        },
      },
      fontFamily: {
        serif: ['"Noto Serif SC"', 'Georgia', 'serif'],
      },
    },
  },
  plugins: [],
}
