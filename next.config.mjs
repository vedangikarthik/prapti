/** @type {import('next').NextConfig} */
const nextConfig = {};

export default { ...nextConfig, ...(process.env.NEXEN_DIST_DIR ? { distDir: process.env.NEXEN_DIST_DIR } : {}) };
