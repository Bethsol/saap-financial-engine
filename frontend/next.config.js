/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Static export for production (baked into the Docker image).
  // 'next dev' is unaffected — output mode only applies to 'next build'.
  output: "export",
  images: { unoptimized: true },
  env: {
    // next build always runs with NODE_ENV=production; next dev with development.
    // Production (Docker): no explicit base → relative fetch("/dashboard/sample").
    // Development: fall back to the local backend if the var isn't set by the script.
    NEXT_PUBLIC_API_BASE:
      process.env.NODE_ENV === "production"
        ? (process.env.NEXT_PUBLIC_API_BASE ?? "")
        : (process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000"),
  },
};
module.exports = nextConfig;
