/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        status: {
          done: '#1D9E75',
          'done-bg': '#E1F5EE',
          pending: '#BA7517',
          'pending-bg': '#FAEEDA',
          missing: '#A32D2D',
          'missing-bg': '#FCEBEB',
        },
      },
    },
  },
  plugins: [],
}
