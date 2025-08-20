/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './marketing/templates/**/*.html',
    './**/*.py'
  ],
  theme: {
    extend: {
      colors: {
        ayder: {
          DEFAULT: '#4F7942',
          dark: '#42673a',
          light: '#E6F0E6'
        }
      },
      fontFamily: {
        display: ['"Playfair Display"', 'serif'],
        sans: ['Manrope', 'Inter', 'ui-sans-serif', 'system-ui']
      }
    }
  },
  plugins: []
}
