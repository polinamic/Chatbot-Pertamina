/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class', // INI KODE BARU YANG DITAMBAHKAN
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        pertaminaBlue: '#0054A6',
        pertaminaRed: '#ED1C24',
        pertaminaGreen: '#009E4D',
      }
    },
  },
  plugins: [],
}