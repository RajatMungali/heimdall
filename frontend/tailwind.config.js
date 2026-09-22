/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      colors: {
        nexa: {
          bg: '#0a0a0f',
          card: '#111118',
          'card-hover': '#16161f',
          surface: '#1a1a24',
          border: '#1e1e2a',
          'border-strong': '#2a2a3a',
          accent: '#e8a43a',
          'accent-bright': '#f0b856',
        },
      },
      animation: {
        'slide-in': 'slide-in 180ms ease-out',
        'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
        'gauge-fill': 'gauge-fill-in 1.2s cubic-bezier(0.4, 0, 0.2, 1) forwards',
        'fade-in': 'fade-in 0.4s ease-out both',
        shimmer: 'shimmer 2s linear infinite',
      },
      keyframes: {
        'slide-in': {
          '0%': { transform: 'translateX(100%)' },
          '100%': { transform: 'translateX(0)' },
        },
        'pulse-glow': {
          '0%, 100%': { opacity: '0.6' },
          '50%': { opacity: '1' },
        },
        'gauge-fill-in': {
          from: { 'stroke-dashoffset': '283' },
        },
        'fade-in': {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          '0%': { 'background-position': '-200% 0' },
          '100%': { 'background-position': '200% 0' },
        },
      },
    },
  },
  plugins: [],
};
