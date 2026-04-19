# Testing Guide

## 백엔드 중심 점검
- 라우트 응답 스모크 테스트
- 전략 로더 AST 검증 테스트
- 백테스트 지표 계산 회귀 테스트
- 채팅 SSE 이벤트 순서 테스트

## 대표 파일
- `server/tests/test_evolution_llm.py`
- `server/tests/test_llm_service.py`
- `server/tests/test_llm_benchmarks.py`
- `server/tests/test_triggers.py`

## 실행 전략
1. 단위 테스트 우선
2. API 스모크(핵심 endpoint)
3. 로컬 대시보드/백테스트 수동 검증
4. 터널/배포 연동 테스트

## 회귀 위험 지점
- Trinity Score 공식(v1/v2) 혼재
- 전략 코드 호환성(legacy generate_signals)
- 네트워크 fallback 순서 변경
