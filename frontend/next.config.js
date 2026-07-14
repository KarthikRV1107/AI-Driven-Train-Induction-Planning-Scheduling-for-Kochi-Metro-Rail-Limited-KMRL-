/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',

  // API proxy rewrites — avoids CORS in production
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
    return [
      {
        source: '/api/v1/:path*',
        destination: `${apiUrl}/api/v1/:path*`,
      },
      {
        source: '/health',
        destination: `${apiUrl}/health`,
      },
    ]
  },

  // Security headers
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          { key: 'X-DNS-Prefetch-Control',    value: 'on'          },
          { key: 'X-Frame-Options',            value: 'SAMEORIGIN'  },
          { key: 'X-Content-Type-Options',     value: 'nosniff'     },
          { key: 'Referrer-Policy',            value: 'strict-origin-when-cross-origin' },
          { key: 'Permissions-Policy',         value: 'camera=(), microphone=(), geolocation=()' },
        ],
      },
    ]
  },

  // Image optimization
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: 'kmrl.in' },
      { protocol: 'https', hostname: 'nexusai.kmrl.in' },
    ],
  },

  // TypeScript and ESLint
  typescript: { ignoreBuildErrors: false },
  eslint:     { ignoreDuringBuilds: false },

  // Experimental
  experimental: {
    optimizePackageImports: ['recharts', 'lucide-react'],
  },

  // Environment
  env: {
    NEXT_PUBLIC_APP_VERSION: '2.4.1',
    NEXT_PUBLIC_APP_NAME:    'KMRL NexusAI',
  },
}

module.exports = nextConfig
