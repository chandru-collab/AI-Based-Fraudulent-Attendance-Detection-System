/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f5f6ff',
          100: '#ebedff',
          200: '#dce0ff',
          300: '#c2c7ff',
          400: '#9fa4ff',
          500: '#7375ff',
          600: '#4e4cff',
          700: '#3c36eb',
          800: '#322cc4',
          900: '#2c279c',
          950: '#1a1661',
        },
        dark: {
          50: '#f6f6f7',
          100: '#eef0f2',
          200: '#dcdfe3',
          300: '#c1c7cd',
          400: '#9ea7b1',
          500: '#7c8896',
          600: '#64707e',
          700: '#525c68',
          800: '#464e57',
          900: '#111827', // Gray 900
          950: '#030712', // Gray 950
        }
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
      boxShadow: {
        glass: '0 8px 32px 0 rgba(31, 38, 135, 0.37)',
        glow: '0 0 15px rgba(115, 117, 255, 0.5)',
      },
      backdropBlur: {
        glass: '12px',
      }
    },
  },
  plugins: [],
}
