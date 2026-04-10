/** @type {import('tailwindcss').Config} */
const colors = require('tailwindcss/colors');

module.exports = {
  content: [
    './templates/**/*.html',
    './Assistant/templates/**/*.html',
    './Moderation/templates/**/*.html',
    './identity_auth/templates/**/*.html',
    './assets_static/**/*.js',
    './home/**/*.py',
    './Blog/**/*.py',
    './Moderation/**/*.py',
    './Assistant/**/*.py',
    './Users/**/*.py',
    './identity_auth/**/*.py',
  ],
  theme: {
    extend: {
      colors: {
        // Полная шкала: в шаблонах встречаются primary-100…800, secondary-100…
        primary: colors.blue,
        secondary: colors.violet,
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      keyframes: {
        fadeIn: {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        slideUp: {
          from: { transform: 'translateY(20px)', opacity: '0' },
          to: { transform: 'translateY(0)', opacity: '1' },
        },
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-in-out',
        'slide-up': 'slideUp 0.5s ease-out',
        'bounce-slow': 'bounce 2s infinite',
      },
    },
  },
  plugins: [],
};
