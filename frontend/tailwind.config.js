/** @type {import('tailwindcss').Config} */
export default {
  // 指定 Tailwind 扫描的文件范围，用于 tree-shaking 未使用的样式
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      // 自定义颜色、字体等可在此扩展
      colors: {
        primary: {
          50: '#eff6ff',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
        },
      },
    },
  },
  plugins: [],
}
