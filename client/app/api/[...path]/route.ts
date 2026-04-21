/**
 * 백엔드 프록시 (catch-all)
 *
 * Next.js rewrites는 외부 요청에 커스텀 헤더를 붙일 수 없어
 * localtunnel의 Bypass 챌린지 페이지를 뚫지 못합니다.
 * 이 핸들러가 rewrites를 대체하며 Bypass 헤더를 명시적으로 추가합니다.
 */

import { NextRequest } from "next/server";

export const runtime = "nodejs"; // SSE 스트리밍을 위해 Node.js 런타임 사용

const getBackendBase = (): string => {
  const raw = (
    process.env.BACKEND_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    (process.env.NODE_ENV === "production"
      ? "https://lsy-super-trend.loca.lt"
      : "http://localhost:8000")
  )
    .trim()
    .replace(/\/+$/, "");
  // '/api' suffix가 붙어 있으면 제거 (base only)
  return raw.endsWith("/api") ? raw.slice(0, -4) : raw;
};

// hop-by-hop 헤더는 fetch로 전달하면 안 됨
const REQUEST_BLOCKED_HEADERS = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
  "host",
  // Upstream 압축을 강제 전달하면 Node fetch의 자동 디코딩과 충돌할 수 있음
  "accept-encoding",
]);

// Response 재구성 시 길이/인코딩 헤더를 그대로 넘기면 바디와 불일치할 수 있음
const RESPONSE_STRIP_HEADERS = new Set([
  "content-encoding",
  "content-length",
  "transfer-encoding",
]);

async function proxyHandler(
  req: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  const { path } = await context.params;
  const url = new URL(req.url);
  const backendBase = getBackendBase();
  const targetUrl = `${backendBase}/api/${path.join("/")}${url.search}`;

  // 클라이언트 헤더 복사 (hop-by-hop 제거)
  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (!REQUEST_BLOCKED_HEADERS.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });
  // localtunnel 챌린지 페이지 우회
  headers.set("Bypass-Tunnel-Reminder", "true");

  // GET/HEAD 는 body 없음
  let body: ArrayBuffer | undefined;
  if (req.method !== "GET" && req.method !== "HEAD") {
    body = await req.arrayBuffer();
  }

  let response: Response;
  try {
    response = await fetch(targetUrl, {
      method: req.method,
      headers,
      body,
    });
  } catch (err) {
    console.error("[proxy] Backend unreachable:", targetUrl, err);
    return new Response(
      JSON.stringify({
        error: "Backend unreachable",
        hint: "터널 URL 또는 BACKEND_API_URL 환경변수를 확인하세요.",
        target: targetUrl,
      }),
      { status: 502, headers: { "Content-Type": "application/json" } }
    );
  }

  // 응답 헤더 복사 (hop-by-hop 제거)
  const resHeaders = new Headers();
  response.headers.forEach((value, key) => {
    const lower = key.toLowerCase();
    if (!REQUEST_BLOCKED_HEADERS.has(lower) && !RESPONSE_STRIP_HEADERS.has(lower)) {
      resHeaders.set(key, value);
    }
  });

  // body 스트림 그대로 전달 (SSE 포함)
  return new Response(response.body, {
    status: response.status,
    headers: resHeaders,
  });
}

export {
  proxyHandler as GET,
  proxyHandler as POST,
  proxyHandler as PUT,
  proxyHandler as DELETE,
  proxyHandler as PATCH,
};
