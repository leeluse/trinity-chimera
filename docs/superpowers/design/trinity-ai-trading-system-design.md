# Trinity AI Trading System: 종합 설계 문서

## 1. 개요

Trinity AI Trading System은 LLM 에이전트가 시장 환경과 성과를 분석하여 자율적으로 트레이딩 전략을 진화시키는 자율 시스템입니다. 본 문서는 시스템의 전체 아키텍처, 핵심 컴포넌트, 데이터 모델 및 구현 상태를 종합적으로 설명합니다.

### 핵심 목표
- **자율 진화**: LLM 에이전트의 지속적인 전략 개선
- **안전한 코드 실행**: 동적 Python 코드 실행을 위한 샌드박스 환경
- **실시간 모니터링**: 성과 및 상태의 실시간 시각화
- **과적합 방지**: IS/OOS 검증을 통한 견고한 전략 검증

## 2. 시스템 아키텍처

### 2.1 전체 구성도

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   프론트엔드     │    │    백엔드 API    │    │   데이터베이스    │
│   대시보드      │◄──►│    서버         │◄──►│   Supabase      │
│  (Next.js)     │    │   (FastAPI)     │    │  (PostgreSQL)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  실시간 차트     │    │ 진화 오케스트레이터 │    │   전략 버전 관리  │
│  에이전트 상태   │    │  (Evolution     │    │   성과 추적      │
│  코드 편집기    │    │  Orchestrator)  │    │   개선 로그      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 2.2 핵심 데이터 흐름

1. **시장 데이터 수집** → **LLM 전략 생성** → **샌드박스 백테스트** → **Trinity Score 계산** → **Supabase 저장** → **다음 진화 주기**

## 3. 핵심 컴포넌트 설계

### 3.1 Dynamic Strategy Sandbox (B-Mode)

**목적**: LLM 생성 코드의 안전한 실행 환경 제공

**구현 상태**: ✅ 완료
- **`StrategyInterface`**: 모든 전략이 구현해야 할 추상 클래스
- **`StrategyLoader`**: AST 기반 정적 분석 및 멀티프로세싱 타임아웃
- **보안 검증**: 금지된 모듈/함수 차단 (`os`, `sys`, `subprocess` 등)

**파일 위치**:
- `ai_trading/core/strategy_interface.py`
- `ai_trading/core/strategy_loader.py`
- `ai_trading/tests/test_sandbox.py` (보안 테스트)

### 3.2 Autonomous Evolution Orchestrator

**목적**: 에이전트의 자율 진화 루프 관리

**구현 상태**: ✅ 완료
- **상태 머신**: `IDLE` → `TRIGGERED` → `GENERATING` → `VALIDATING` → `COMMITTING`
- **적응형 트리거**: 4단계 트리거 시스템 (Regime-Shift, Performance Decay, Competitive Pressure, Heartbeat)
- **Self-Correction**: 최대 3회 재생성 루프

**파일 위치**:
- `api/services/evolution_orchestrator.py`

### 3.3 Robust Backtesting Engine

**목적**: 견고한 성과 검증 시스템

**구현 상태**: ✅ 완료
- **IS/OOS Splitter**: 과적합 방지를 위한 인샘플/아웃샘플 분할
- **Conservative Cost Model**: 현실적인 수수료 및 슬리피지 모델
- **Validation Gate**: OOS 성과가 IS 성과의 70% 이상 필수

**파일 위치**:
- `ai_trading/core/backtest_manager.py`
- `ai_trading/core/cost_model.py`

### 3.4 Trinity Score 계산 시스템

**목적**: 종합적인 전략 평가 지표

**공식**:
```
Trinity Score = Return × 0.4 + Sharpe × 25 × 0.35 + (1 + MDD) × 100 × 0.25
```

**특징**:
- 수익성(Return), 위험조정수익률(Sharpe), 하방위험(MDD)의 균형
- 표준화된 비교 가능한 단일 지표

## 4. 데이터베이스 설계

### 4.1 스키마 구조

**구현 상태**: ✅ 완료 (Supabase 적용 완료)

**테이블 구성**:
- **`agents`**: 에이전트 기본 정보 및 현재 전략
- **`strategies`**: 전략 버전 관리 (LLM 생성 코드 저장)
- **`backtest_results`**: 성과 추적 및 Trinity Score 저장
- **`improvement_logs`**: 진화 이력 및 피드백 저장

**인덱스**:
- `idx_strategies_agent_id`: 에이전트별 전략 조회 최적화
- `idx_backtest_strategy_id`: 전략별 성과 조회 최적화
- `idx_improvement_agent_id`: 개선 이력 조회 최적화

### 4.2 실시간 기능

**Supabase Realtime**을 활용한 실시간 업데이트:
- `backtest_results` INSERT 이벤트 구독
- `strategies` INSERT 이벤트 구독  
- `agents` UPDATE 이벤트 구독

## 5. 프론트엔드 설계

### 5.1 대시보드 구성

**구현 상태**: ✅ 완료 (`front/app/v2/page.tsx`)

**주요 기능**:
- **실시간 차트**: Trinity Score 및 다양한 메트릭 시각화
- **에이전트 카드**: 상태 및 성과 표시
- **코드 편집기**: Monaco Editor 통합
- **백테스트 요약**: 성과 비교 테이블

**실시간 기능**:
- 지수 백오프 재연결 로직
- 에러 핸들링 및 수동 재연결
- 로딩 상태 관리

### 5.2 컴포넌트 구조

- **`AgentCard`**: 에이전트 상태 표시 컴포넌트
- **`LogCard`**: 진화 로그 및 파라미터 변경 내역
- **`CodeEditor`**: 전략 코드 표시 편집기

## 6. API 설계

### 6.1 주요 엔드포인트

**구현 상태**: ✅ 완료

| 엔드포인트 | 기능 | 데이터 소스 |
|-----------|------|-------------|
| `/api/agents/{id}/evolve` | 강제 진화 트리거 | Evolution Orchestrator |
| `/api/agents/{id}/status` | 상태 조회 | Supabase `agents` |
| `/api/agents/{id}/backtest` | 최신 성과 조회 | Supabase `backtest_results` |
| `/api/dashboard/metrics` | 대시보드 메트릭 | Supabase 집계 쿼리 |

### 6.2 에러 핸들링

- **타임아웃 처리**: 멀티프로세싱 기반 30초 제한
- **보안 예외**: 금지된 코드 실행 차단
- **데이터 무결성**: 외래키 제약 조건

## 7. 보안 설계

### 7.1 코드 실행 보안

**AST 정적 분석**:
- 금지된 키워드 사전 검사
- 위험한 함수 호출 차단
- 코드 구조 검증

**실행 격리**:
- 멀티프로세싱 기반 격리 실행
- 리소스 제한 설정
- 무한 루프 방지

### 7.2 데이터 보안

**RLS (Row Level Security)**:
- 에이전트별 데이터 접근 제한
- 읽기/쓰기 권한 분리
- 감사 로그 저장

## 8. 모니터링 및 로깅

### 8.1 성과 모니터링

**실시간 지표**:
- Trinity Score 추이
- Sharpe Ratio 변화
- 최대 낙폭(MDD) 추적
- 승률 변화

**에이전트 상태**:
- 현재 전략 버전
- 마지막 진화 시간
- 상태 변화 이력

### 8.2 시스템 모니터링

**건강 상태**:
- 데이터베이스 연결 상태
- LLM API 응답 시간
- 백테스트 실행 성공률

## 9. 구현 상태 요약

### 9.1 완료된 기능

| 컴포넌트 | 구현 상태 | 테스트 상태 |
|----------|-----------|-------------|
| Dynamic Strategy Sandbox | ✅ 완료 | ✅ 통과 |
| Evolution Orchestrator | ✅ 완료 | ✅ 통과 |
| Backtesting Engine | ✅ 완료 | ✅ 통과 |
| Supabase 통합 | ✅ 완료 | ✅ 통과 |
| 프론트엔드 대시보드 | ✅ 완료 | ✅ 통과 |
| 실시간 업데이트 | ✅ 완료 | ✅ 통과 |

### 9.2 남은 작업

- **통합 테스트**: 전체 시스템 E2E 테스트
- **성능 최적화**: 대규모 데이터 처리 최적화
- **배포 구성**: 프로덕션 환경 설정

## 10. 확장성 고려사항

### 10.1 수평 확장

**에이전트 확장**:
- 동적 에이전트 생성 지원
- 리소스 풀 기반 관리
- 부하 분산 구성

**데이터 확장**:
- 분할된 데이터베이스 설계
- 캐싱 레이어 추가
- 배치 처리 최적화

### 10.2 기능 확장

**추가 기능**:
- 멀티 자산 지원
- 다양한 트레이딩 전략 템플릿
- 커스텀 메트릭 지원

## 11. 결론

Trinity AI Trading System은 LLM 기반 자율 트레이딩 시스템의 완전한 구현체입니다. 안전한 코드 실행, 견고한 성과 검증, 실시간 모니터링을 통해 프로덕션 환경에서 안정적으로 운영될 수 있는 아키텍처를 갖추고 있습니다.

현재 시스템은 기본적인 자율 진화 루프를 완성하였으며, 추가적인 통합 테스트와 성능 최적화를 통해 완성도를 더욱 높일 수 있습니다.