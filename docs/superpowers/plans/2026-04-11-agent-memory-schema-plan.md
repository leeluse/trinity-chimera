# 2026-04-11 Agent Memory Schema Plan

## Goal

페르소나 기반 에이전트를 넘어, **기억과 성과에 따라 장기적으로 정체성이 형성되는 자아형 트레이딩 에이전트**를 위해 필요한 메모리 스키마를 설계한다.

이 계획의 산출물은 다음 두 가지다.

1. 사람이 읽는 설계 문서
2. 추후 구현에 바로 옮길 수 있는 machine-readable schema 초안

## Non-Goals

- 이번 단계에서 실제 백엔드/프론트엔드 코드 구현은 하지 않는다.
- Supabase 테이블 생성이나 API 엔드포인트 추가는 하지 않는다.
- 기존 에이전트 로직을 바로 교체하지 않는다.

## Design Questions

- 자아형 에이전트의 **고정 정체성**과 **가변 기억**을 어떻게 분리할 것인가?
- 기억 누적으로 인한 프롬프트 비만을 어떻게 방지할 것인가?
- 충돌하는 경험(`A에선 먹힘`, `B에선 안 먹힘`)을 어떻게 저장할 것인가?
- 어떤 데이터는 archive로 보내고, 어떤 데이터만 active state에 남길 것인가?
- 사람이 이해하는 문서와 LLM이 읽는 상태 객체를 어떻게 분리할 것인가?

## Deliverables

- [ ] `docs/superpowers/specs/2026-04-11-agent-memory-schema.md`
  - 자아형 에이전트 메모리 계층 구조
  - 상태 객체 필드 정의
  - 기억 압축/요약/검색 규칙
  - 운영 흐름(언제 무엇을 읽고, 언제 무엇을 갱신하는지)
- [ ] `research.md`
  - 본 설계의 판단 근거와 제약 업데이트
- [ ] 구현 전 체크리스트
  - 어떤 파일/테이블/API가 이후 구현 대상인지 식별

## Proposed Schema Scope

### 1. Core Identity Layer

- agent_id
- strategy_bias
- risk_profile
- immutable_constraints
- primary_objectives

### 2. State Snapshot Layer

- current_strengths
- current_weaknesses
- recent_success_patterns
- recent_failure_patterns
- preferred_mutations
- blocked_mutations
- confidence_summary

### 3. Episodic Memory Layer

- event_id
- version_id
- regime_context
- volatility_context
- liquidity_context
- action_taken
- result_metrics
- lesson_candidate
- confidence

### 4. Derived Rule Layer

- rule_id
- condition_set
- recommended_action
- anti_pattern
- evidence_count
- confidence_score
- last_verified_at

### 5. Archive Layer

- full raw event history
- discarded hypotheses
- superseded summaries

## Planned Work Steps

- [ ] Step 1. 현재 프로젝트 맥락에 맞는 자아형 에이전트 메모리 요구사항 정리
- [ ] Step 2. 메모리 계층(Identity / Snapshot / Episodic / Rule / Archive) 정의
- [ ] Step 3. 각 계층의 필드 스키마 초안 작성
- [ ] Step 4. retrieval / compression / decay 규칙 정의
- [ ] Step 5. 현재 Trinity 구조(`agents`, `backtest`, `dashboard`)와 연결 지점 명시
- [ ] Step 6. 구현 전환 시 필요한 테이블/API/파일 후보 명시

## Risks to Address

- 메모리 누적으로 인한 prompt obesity
- 충돌 경험 누적으로 인한 self-story 오염
- 사람이 읽는 문서와 모델 상태 객체가 섞이는 문제
- 성격만 있고 실제 성과 차이는 없는 fake personality
- 지나친 자유도로 인한 drift

## Approval Gate

이 계획이 승인되면 다음 단계로 아래 작업을 진행한다.

1. `docs/superpowers/specs/2026-04-11-agent-memory-schema.md` 작성
2. `research.md`에 설계 결론 반영
3. 구현 전 체크리스트 정리
