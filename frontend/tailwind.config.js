/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        space: {
          50: '#1b120c',
          100: '#261912',
          200: '#38251c',
          300: '#4d372c',
          400: '#6c5649',
          500: '#8a7466',
          600: '#a89486',
          700: '#c5b4a5',
          800: '#ded2c5',
          850: '#ede2d6',
          900: '#ffffff',
          950: '#f6f1ec',
        },
        accent: {
          50: '#fdf8f4',
          100: '#faeee5',
          200: '#f4dcce',
          300: '#e9beaa',
          400: '#b45f23',
          500: '#964f19', // Warm Roasted Caramel Bronze
          600: '#7c3d10',
          700: '#642f0a',
          800: '#4a2206',
          900: '#331603',
        },
        tealx: {
          300: '#86efac',
          400: '#22c55e',
          500: '#166534', // Precision Sage Forest
          600: '#14532d',
        },
        amberx: {
          300: '#fde047',
          400: '#f59e0b',
          500: '#b45309', // Roasted Warm Amber
          600: '#92400e',
        },
        redx: {
          300: '#fca5a5',
          400: '#ef4444',
          500: '#b91c1c', // Deep Espresso Crimson
          600: '#991b1b',
        },
        violetx: {
          300: '#d8b4fe',
          400: '#a855f7',
          500: '#582f0e', // Dark Mocha Roast
          600: '#3d1f08',
        },
      },
      fontFamily: {
        display: ['Rajdhani', 'Sora', 'sans-serif'],
        sans: ['Sora', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
      },
      boxShadow: {
        'glow-accent': '0 0 16px -2px rgba(150, 79, 25, 0.25)',
        'glow-teal': '0 0 16px -2px rgba(22, 101, 52, 0.25)',
        'glow-red': '0 0 16px -2px rgba(185, 28, 28, 0.25)',
        'coffee-card': '0 1px 3px rgba(38, 25, 18, 0.05), 0 1px 2px rgba(38, 25, 18, 0.03)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'blink': 'blink 1.2s infinite',
        'spin-slow': 'spin 20s linear infinite',
      },
      keyframes: {
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.2' },
        },
      },
    },
  },
  plugins: [],
};
