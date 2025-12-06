/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    serverActions: {
      bodySizeLimit: '2mb'
    }
  },
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**'
      }
    ]
  },
  async headers() {
    const isDev = process.env.NODE_ENV !== 'production';
    const connectSrc = [
      "'self'",
      'https://www.googleapis.com',
      'https://accounts.google.com',
      'https://api.openai.com'
    ];

    const extraOrigins = [process.env.LLM_API_URL, process.env.NEXT_PUBLIC_AUTH_API_URL, process.env.NEXT_PUBLIC_AUTH_API_BASE]
      .filter(Boolean)
      .map((value) => {
        try {
          return new URL(value).origin;
        } catch (error) {
          return null;
        }
      })
      .filter(Boolean);

    connectSrc.push(...extraOrigins);

    const csp = [
      "default-src 'self'",
      // Next.js injects small inline hydration/runtime scripts; keep inline until moved to a nonce-based policy.
      "script-src 'self' 'unsafe-inline'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: https:",
      "font-src 'self' data:",
      `connect-src ${connectSrc.join(' ')}`,
      "frame-src 'self' https://accounts.google.com",
      "worker-src 'self'",
      "manifest-src 'self'",
      "object-src 'none'",
      "base-uri 'self'",
      "frame-ancestors 'self' http://localhost:8000 http://127.0.0.1:8000",
      "form-action 'self'"
    ].join('; ');

    const securityHeaders = [
      {
        key: 'Content-Security-Policy',
        value: csp
      },
      ...(!isDev
        ? [
            {
              key: 'X-Frame-Options',
              value: 'DENY'
            }
          ]
        : []),
      {
        key: 'X-Content-Type-Options',
        value: 'nosniff'
      },
      {
        key: 'Referrer-Policy',
        value: 'strict-origin-when-cross-origin'
      },
      {
        key: 'Permissions-Policy',
        value: 'geolocation=(), microphone=(), camera=()'
      },
      {
        key: 'Strict-Transport-Security',
        value: 'max-age=63072000; includeSubDomains; preload'
      }
    ];

    return [
      {
        source: '/(.*)',
        headers: securityHeaders
      }
    ];
  }
};

export default nextConfig;
