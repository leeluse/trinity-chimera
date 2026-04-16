# Troubleshooting

## 1) Vercel에서 `Failed to fetch`
체크:
1. `NEXT_PUBLIC_API_URL`/`BACKEND_API_URL` 값이 최신 터널 URL인지
2. 터널 URL이 실제로 응답하는지 (`/api/system/status`)
3. 터널이 503(`Tunnel Unavailable`) 상태인지 로그 확인

## 2) 채팅은 되는데 대시보드만 실패
원인 후보:
- 채팅과 대시보드가 서로 다른 백엔드 경로를 참조
해결:
- `client/lib/api.ts`의 base URL 우선순위 통일 상태 확인

## 3) 전략 로드 실패 (추상 메서드)
메시지 예: `generate_signal`, `get_params` 미구현
대응:
- `StrategyLoader._ensure_strategy_interface_compat`가 패치 가능한 형태인지 확인
- 클래스 구조가 `StrategyInterface` 기대와 맞는지 확인

## 4) `No module named 'lettrade'`
원인:
- DB 저장 전략 코드가 현재 런타임에 없는 외부 라이브러리 import
대응:
- 전략 코드에서 비허용/미설치 모듈 제거 후 재저장

## 5) run script 동작 확인 포인트
- `./run public-status`
- `logs/localtunnel-8000.log`
- `logs/backend_tunnel_url.txt`

## 6) 코드 동기화 점검 포인트
- Evolution router와 orchestrator 시그니처 인자명(`force_trigger` vs `force`) 정합성 확인
