# Runbook

## 로컬 개발
```bash
./run server
./run client
```

## 공용 접근(localtunnel)
```bash
./run public
./run public-status
./run public-stop
```

## 로그 위치
- API 로그: `logs/api-8000.log`
- Tunnel 로그: `logs/localtunnel-8000.log`
- 현재 터널 URL: `logs/backend_tunnel_url.txt`

## 자동화 루프 운용
- 조회: `GET /api/system/automation`
- 켜기/끄기: `POST /api/system/automation` (`{"enabled": true|false}`)

## 테스트
```bash
./run test
```
참고: 현재 `run test`는 `server/ai_trading/tests/*` 경로를 가리키므로 모듈 구조와 맞는지 주기 점검 필요.
