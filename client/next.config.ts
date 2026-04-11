import type { NextConfig } from "next";

const rawBackendUrl = (
  process.env.BACKEND_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000"
).replace(/\/+$/, "");

const backendBase = rawBackendUrl.endsWith("/api")
  ? rawBackendUrl.slice(0, -4)
  : rawBackendUrl;

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendBase}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
