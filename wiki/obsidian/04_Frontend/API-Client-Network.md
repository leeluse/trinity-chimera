# API Client & Network

## 파일
`client/lib/api.ts`

## 핵심 설계
- 기본 endpoint는 상대경로 `/api`
- `NEXT_PUBLIC_API_URL`가 있으면 우선 direct base 사용
- 실패 시 candidate fallback 순회
- `ngrok-skip-browser-warning`, `Bypass-Tunnel-Reminder` 헤더 부착
- timeout 기본값: 30000ms

## rewrite
`client/next.config.ts`
- `/api/:path* -> {backendBase}/api/:path*`
- backendBase는 `BACKEND_API_URL` 또는 `NEXT_PUBLIC_API_URL`

## 운영 팁
- Vercel에서는 `NEXT_PUBLIC_API_URL`을 명시하는 편이 디버깅이 쉽다.
- 터널/백엔드가 느린 경우 `NEXT_PUBLIC_API_FETCH_TIMEOUT_MS`를 조정.
