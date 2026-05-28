import type { NextConfig } from 'next'

const config: NextConfig = {

  // ── Strict React mode ──────────────────────────────
  reactStrictMode: true,

  // ── Image domains (drone camera stills) ───────────
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: '**.blob.core.windows.net' },
      { protocol: 'http',  hostname: 'localhost' },
    ],
  },

  // ── Webpack: handle Three.js / Mapbox GL ──────────
  webpack(cfg) {
    cfg.module.rules.push({
      test: /.(glsl|vs|fs|vert|frag)$/,
      use:  'raw-loader',
    })
    // Mapbox GL worker (required for map rendering)
    cfg.resolve.alias = {
      ...cfg.resolve.alias,
      'mapbox-gl': 'mapbox-gl/dist/mapbox-gl.js',
    }
    return cfg
  },

  // ── API proxy → FastAPI backend ────────────────────
  async rewrites() {
    return [
      {
        source:      '/api/:path*',
        destination: `${process.env.BACKEND_URL ?? 'http://localhost:8000'}/:path*`,
      },
    ]
  },

  // ── Security headers ───────────────────────────────
  async headers() {
    return [{
      source: '/(.*)',
      headers: [
        { key: 'X-Frame-Options',        value: 'DENY' },
        { key: 'X-Content-Type-Options', value: 'nosniff' },
        { key: 'Referrer-Policy',        value: 'strict-origin' },
      ],
    }]
  },
}

export default config