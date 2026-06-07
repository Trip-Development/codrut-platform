/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async rewrites() {
    const backendUrl = process.env.INTERNAL_API_BASE_URL || "http://backend:8000/api";
    const destination = backendUrl.endsWith("/api") ? `${backendUrl}/:path*` : `${backendUrl}/api/:path*`;
    return [
      {
        source: "/api/:path*",
        destination: destination,
      },
    ];
  },
};

export default nextConfig;
