/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#e6f5ec',
          100: '#b3e0c5',
          200: '#80cb9e',
          300: '#4db677',
          400: '#1aa150',
          500: '#028a39',
          600: '#027a32',
          700: '#016a2b',
          800: '#015a24',
          900: '#014a1d',
        },
      },
    },
  },
  plugins: [],
}
