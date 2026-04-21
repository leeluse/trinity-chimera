# Deployment: Vercel + Tunnel

## 권장 구성
Vercel(Frontend) + 집 PC FastAPI(Backend) + localtunnel 고정 서브도메인.

## 절차
1. PC에서 백엔드 실행
```bash
./run server
```

2. 터널 실행
```bash
./run public
```

3. URL 확인
```bash
cat logs/backend_tunnel_url.txt
```

4. Vercel 환경변수 설정
- `NEXT_PUBLIC_API_URL=https://<subdomain>.loca.lt`
- `BACKEND_API_URL=https://<subdomain>.loca.lt`

5. Vercel 재배포

## 안정화 포인트
- 터널 실패 시 `run` 스크립트의 auto-reconnect가 재시도.
- 터널 URL은 `logs/backend_tunnel_url.txt`를 단일 소스로 사용.
- 프론트는 `client/lib/api.ts`에서 direct base 우선 + fallback.
