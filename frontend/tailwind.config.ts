import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './services/**/*.{ts,tsx}',
  ],

  theme: {
    extend: {

      // ── Brand colours ───────────────────────────────
      colors: {
        swarm:   { DEFAULT: '#1fffb0', dim: '#1fffb030' },
        alert:   { DEFAULT: '#f38ba8' },
        warn:    { DEFAULT: '#fab387' },
        hedera:  { DEFAULT: '#cba6f7' },
        fabric:  { DEFAULT: '#89b4fa' },
      },

      // ── Dark-first background tokens ─────────────────
      backgroundColor: {
        background: 'hsl(var(--background))',
        secondary:  'hsl(var(--secondary))',
        card:       'hsl(var(--card))',
      },

      textColor: {
        foreground:       'hsl(var(--foreground))',
        'muted-foreground': 'hsl(var(--muted-foreground))',
      },

      // ── Mono font for telemetry / console ────────────
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },

      // ── Animation: radar sweep pulse ─────────────────
      keyframes: {
        pulse_dim: {
          '0%, 100%': { opacity: '1' },
          '50%':      { opacity: '0.4' },
        },
      },
      animation: {
        pulse_dim: 'pulse_dim 2s ease-in-out infinite',
      },
    },
  },

  plugins: [],
}

export default config