import type { NextConfig } from "next"

const nextConfig: NextConfig = {
  // Self-contained server bundle for the Docker image.
  output: "standalone",
  // The development badge overlapped the sidebar's account menu. Errors still show.
  devIndicators: false,
}

export default nextConfig
