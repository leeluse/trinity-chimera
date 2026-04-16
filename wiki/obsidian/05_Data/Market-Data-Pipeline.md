# Market Data Pipeline

## 파일
`server/shared/market/provider.py`

## 소스
- Binance Futures Kline API
- endpoint: `https://fapi.binance.com/fapi/v1/klines`

## 지원 인터벌
- `1m`, `5m`, `15m`, `1h`, `4h`

## 처리 단계
1. 심볼 정규화 (`BTC/USDT` -> `BTCUSDT`)
2. 구간(start/end) 기반 chunk fetch
3. DataFrame 변환
4. timestamp 정렬 + 중복 제거
5. API payload(candles) 직렬화

## 연동 포인트
- 백테스트 런타임 `run_skill_backtest()`
- 채팅 마이닝 모드의 고급 백테스트
