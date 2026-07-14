/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{ts,tsx,js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Backgrounds
        'bg-0': '#040608',
        'bg-1': '#080c10',
        'bg-2': '#0d1219',
        'bg-3': '#121922',
        'bg-4': '#1a2332',
        // Borders
        'border-base': '#1e2d40',
        'border-2':    '#253548',
        // Brand
        blue:   { DEFAULT: '#3b82f6', dim: '#1d4ed8' },
        emerald: { DEFAULT: '#10b981', dim: '#059669' },
        amber:  { DEFAULT: '#f59e0b' },
        red:    { DEFAULT: '#ef4444' },
        purple: { DEFAULT: '#8b5cf6' },
        // Text
        'text-0': '#f0f4f8',
        'text-1': '#94a3b8',
        'text-2': '#64748b',
        'text-3': '#334155',
      },
      fontFamily: {
        sans: ['var(--font-sans)', 'Space Grotesk', 'sans-serif'],
        mono: ['var(--font-mono)', 'JetBrains Mono', 'monospace'],
      },
      fontSize: {
        '2xs': ['10px', '14px'],
        xs:    ['11px', '16px'],
        sm:    ['12px', '18px'],
        base:  ['13px', '20px'],
        md:    ['14px', '20px'],
        lg:    ['16px', '24px'],
        xl:    ['18px', '26px'],
        '2xl': ['22px', '30px'],
        '3xl': ['28px', '36px'],
      },
      borderRadius: {
        DEFAULT: '6px',
        md: '10px',
        lg: '16px',
        xl: '20px',
      },
      boxShadow: {
        'glow-blue':   '0 0 20px rgba(59,130,246,.15)',
        'glow-green':  '0 0 20px rgba(16,185,129,.12)',
        'glow-amber':  '0 0 20px rgba(245,158,11,.12)',
        'glow-red':    '0 0 20px rgba(239,68,68,.12)',
        'glow-purple': '0 0 20px rgba(139,92,246,.12)',
        card: '0 4px 16px rgba(0,0,0,.5)',
      },
      animation: {
        'fade-up':   'fade-up .25s ease forwards',
        'fade-in':   'fade-in .2s ease forwards',
        'shimmer':   'shimmer 1.4s infinite',
        'pulse-dot': 'pulse-dot 2s infinite',
      },
      keyframes: {
        'fade-up': {
          from: { opacity: 0, transform: 'translateY(8px)' },
          to:   { opacity: 1, transform: 'translateY(0)' },
        },
        'fade-in': {
          from: { opacity: 0 },
          to:   { opacity: 1 },
        },
        shimmer: {
          '0%':   { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'pulse-dot': {
          '0%, 100%': { opacity: 1, transform: 'scale(1)' },
          '50%':      { opacity: .5, transform: 'scale(.8)' },
        },
      },
      spacing: {
        'sidebar': '200px',
        'topbar':  '52px',
        'cmdbar':  '36px',
      },
    },
  },
  plugins: [],
}
