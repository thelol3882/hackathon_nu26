import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  env: {
    NEXT_PUBLIC_WS_WIRE_FORMAT: process.env.WIRE_FORMAT ?? 'json',
  },
};

export default nextConfig;
