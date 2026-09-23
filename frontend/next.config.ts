import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // ブラウザは localhost:3000/api/... にだけリクエストを送り、web コンテナが
  // compose ネットワーク内で api コンテナへ転送する。ブラウザから見ると同一オリジンなので
  // CORS の設定が要らない。→ docs/notes/topic-same-origin-and-cors.md
  // :path* は「/ を含む残りのパス全部」に一致し、同じ名前で destination に埋め込める。
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://api:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
