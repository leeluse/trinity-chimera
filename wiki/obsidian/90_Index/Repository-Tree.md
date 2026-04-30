# Repository Tree (핵심)

```text
trinity-chimery/
├─ client/
│  ├─ app/
│  │  ├─ page.tsx
│  │  └─ backtest/BacktestClientPage.tsx
│  ├─ components/
│  │  ├─ features/crime/
│  │  │  ├─ engine/
│  │  │  │  ├─ crimeEngine.ts        # REST 스캔 (레거시)
│  │  │  │  └─ crimeWsEngine.ts      # WS 기반 엔진 (현재)
│  │  │  ├─ CrimeDashboard.tsx
│  │  │  └─ CrimeMainPanel.tsx
│  │  └─ charts/CandleStickChart.tsx
│  ├─ store/useCrimeStore.ts          # WS 엔진 연동 상태
│  ├─ lib/api.ts
│  └─ next.config.ts
├─ server/
│  ├─ api/main.py
│  ├─ modules/
│  │  ├─ chat/
│  │  │  └─ skills/
│  │  │     ├─ pipeline_regime.py    # 레짐 귀속 분석 (신규)
│  │  │     └─ pipeline_optimize.py
│  │  ├─ evolution/
│  │  ├─ engine/
│  │  └─ backtest/
│  ├─ strategies/                    # 전략 파일 (직접 임포트용)
│  │  ├─ robust_signal_v2_optimized.py   # 룩어헤드 수정 완료
│  │  ├─ quant_trend_engine_v3.py
│  │  └─ regime_controller_v1.py
│  └─ shared/
│     ├─ db/supabase.py
│     ├─ llm/
│     └─ market/
│        └─ provider.py              # Bybit OHLCV (2026-04-28~)
├─ scripts/
│  └─ strategy_league_campaign.py   # 전략 성능 벤치마크 스크립트
├─ run
└─ wiki/obsidian/
```

## 상세 탐색 링크
- [[Module-Map]]
- [[API-Reference]]
- [[Route-Map]]
