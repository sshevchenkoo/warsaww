import type { NextConfig } from "next";

// In dev the API is a separate origin (:8000). Proxy the cookie-bearing paths
// through Next so the session cookie is first-party to the web origin (cookies
// wouldn't survive cross-origin otherwise). /search needs the cookie too now,
// for the per-session rate limit. In production the ingress already serves web
// + API from one domain, so these paths are same-origin there too.
const BACKEND = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone", // self-contained server bundle for the Docker image
  async rewrites() {
    return [
      { source: "/auth/:path*", destination: `${BACKEND}/auth/:path*` },
      { source: "/me", destination: `${BACKEND}/me` },
      { source: "/me/:path*", destination: `${BACKEND}/me/:path*` },
      { source: "/search", destination: `${BACKEND}/search` },
    ];
  },
};

export default nextConfig;
