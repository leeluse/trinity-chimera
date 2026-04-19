import type { NextConfig } from "next";

/**
 * ⚠️ /api/:path* rewrite는 제거되었습니다.
 *
 * 이유: Next.js rewrites는 외부 요청에 커스텀 헤더를 추가할 수 없어
 * localtunnel(loca.lt) Bypass 챌린지 페이지를 통과하지 못합니다.
 *
 * 대신 app/api/[...path]/route.ts 프록시 핸들러를 사용합니다.
 * 해당 핸들러가 Bypass-Tunnel-Reminder 헤더를 자동으로 추가합니다.
 */
const nextConfig: NextConfig = {};

export default nextConfig;
