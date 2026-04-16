---
tags: [moc, home]
---

# Home

프로젝트 전반을 빠르게 파악하기 위한 시작 노트.

## Quick Links
- [[Quickstart]]
- [[Project-Overview]]
- [[Core-Features]]
- [[System-Architecture]]
- [[Execution-Flow]]
- [[Module-Map]]
- [[API-Reference]]
- [[Evolution-Memory-Workflow]]
- [[Dashboard-UI]]
- [[Backtest-UI]]
- [[Database-Model]]
- [[Runbook]]
- [[Troubleshooting]]
- [[Recent-Changes-2026-04]]

## 현재 시스템 한 줄 요약
멀티 에이전트(4개)가 전략을 생성/검증/개선하며, 대시보드와 채팅 UI에서 수동 루프와 자동 루프를 함께 운영하는 트레이딩 실험 플랫폼.

## 핵심 엔트리 포인트
- Backend Entry: `server/api/main.py`
- Frontend Entry: `client/app/page.tsx`, `client/app/backtest/BacktestClientPage.tsx`
- Runner Script: `run`
