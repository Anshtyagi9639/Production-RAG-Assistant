import type { NextConfig } from "next"

const nextConfig: NextConfig = {
  // Self-contained server bundle for the Docker image.
  output: "standalone",
  // The development badge overlapped the sidebar's account menu. Errors still show.
  devIndicators: false,
  // Pages declare icon.svg, but browsers still request /favicon.ico; answer with the same icon.
  async rewrites() {
    return [{ source: "/favicon.ico", destination: "/icon.svg" }]
  },
}

export default nextConfig
