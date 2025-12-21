import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: [
    './app/**/*.{js,ts,jsx,tsx}',
    './components/**/*.{js,ts,jsx,tsx}',
    './lib/**/*.{js,ts,jsx,tsx}'
  ],
  theme: {
    extend: {
      colors: {
        surface: 'var(--bg-surface)',
        'surface-dark': 'var(--bg-elevated)',
        accent: 'var(--accent)',
        'accent-strong': 'var(--accent-strong)',
        'text-primary': 'var(--text-primary)',
        'text-muted': 'var(--text-muted)',
        border: 'var(--border-subtle)'
      },
      fontFamily: {
        sans: ['"Inter"', '"SF Pro Display"', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace']
      },
      borderRadius: {
        xl: '20px',
        '2xl': '24px',
        pill: '999px'
      },
      boxShadow: {
        card: 'var(--shadow-soft)'
      }
    }
  },
  plugins: []
};

export default config;
