# Evolution System

## 핵심 컴포넌트
- Orchestrator: `server/modules/evolution/orchestrator.py`
- Trigger: `server/modules/evolution/trigger.py`
- State Manager: `server/modules/evolution/agents.py`
- LLM Brain: `server/modules/evolution/llm.py`
- Evolution Backtest: `server/modules/backtest/evolution/evolution_engine.py`

## 실행 단계
1. per-agent Lock 확인 (중복 실행 방지)
2. LLM Circuit Breaker 확인 (연속 실패 시 대기)
3. 트리거 조건 확인
4. 현재 전략 로딩(Supabase)
5. LLM 코드 생성 (`generate_signal` 함수 방식)
6. 후보 코드 검증 (Quick Gate → Full Gate)
7. 점수 비교 후 채택/거절
8. 상태를 IDLE로 복귀

## 상태 머신
- `IDLE`
- `TRIGGERED`
- `GENERATING`
- `VALIDATING`
- `COMMITTING`

## 이벤트 로깅
`AgentStateManager`가 `add_event()`로 메모리 로그(deque maxlen=600) 유지.

## 트리거 정책
`EvolutionTrigger.check_trigger()`는 heartbeat 분(min) 간격으로 동작.
환경 변수: `EVOLUTION_HEARTBEAT_MINUTES`

## 점수 기준
`server/modules/evolution/scoring.py`
- `calculate_trinity_score()`
- `evaluate_improvement(baseline, candidate)`

---

## 안정성 개선 (2026-04-17)

### 1. per-agent async Lock
`EvolutionOrchestrator._agent_locks[agent_id]`로 에이전트별 동시 실행을 차단한다.
같은 에이전트가 이미 실행 중이면 즉시 return → 중복 폭탄(duplicate flood) 방지.

```python
# orchestrator.py
lock = self._agent_locks.setdefault(agent_id, asyncio.Lock())
if lock.locked(): return           # 이미 실행 중
async with lock:
    await self._run_evolution_cycle_inner(...)
```

### 2. LLM Circuit Breaker
연속 5회 LLM 실패 시 300초(5분) 자동 대기. 성공 시 카운터 리셋.
- `self._llm_consecutive_failures` : 연속 실패 횟수
- `self._llm_backoff_until` : 해제 시각(epoch)
- 임계값 환경변수로 조정 가능 (`_LLM_FAILURE_THRESHOLD`, `_LLM_BACKOFF_SECONDS`)

### 3. LLM 프롬프트 통일 (함수 방식)
`strategy_from_code()`는 `generate_signal(train_df, test_df)` 함수를 **1순위**로 처리한다.
클래스 방식(행별 루프)은 2순위이며 느리고 오류가 많다.
프롬프트를 함수 방식으로 통일하여 코드 생성 성공률을 높였다.

→ 자세한 내용은 [[Strategy-Code-Spec]] 참고

---

## 코드 품질 개선 (2026-04-20)

### 1. Self-Critique 루프

코드 생성 후 `StrategyLoader.validate_code()` 통과 시 `_self_critique()` 추가 검증.
temperature=0.1 (결정론적)으로 3가지 YES/NO 질문을 검사한다:

| 질문 | 실패 조건 | 재생성 지시 |
|---|---|---|
| Q1: 숏(-1) 신호 존재? | NO | 양방향 신호 구현 강제 |
| Q2: AND 조건 4개 이상? | YES | 조건 3개 이하로 축소 |
| Q3: 미정의 변수 참조? | YES | 선언 전 참조 금지 |

실패 시 `last_error`에 추가하고 재시도. `max_retries` 소진 시 마지막 코드를 반환(실행 보장).

### 2. Few-Shot 코드 스니펫 주입

`memory_context["best_code_snippet"]`에 저장된 최고 성능 전략의 핵심 코드 블록을
프롬프트 Section 10에 참고용으로 주입 (`_assemble_prompt()`).

- `wiki_memory.py::get_best_code_snippet(agent_id)` — 에이전트별 최고 채택 전략 코드 반환
- `wiki_memory.py::_extract_signal_block(code, max_lines=25)` — sig 생성 블록 추출
- `wiki_memory.py::log_accepted(..., code=)` — 채택 시 `code_snippet` 저장

### 3. Temperature 분리

- 코드 생성 호출: `temperature=0.3`
- Self-critique: `temperature=0.1`

→ 자세한 모델별 temperature는 [[LLM-Model-Roles]] 참고

## 주의 포인트
- `router.py`에서 `force_trigger` 인자를 사용하는 호출이 있으며, 오케스트레이터 함수 시그니처(`force`)와 동기화 확인 필요.
- 진화 루프 실행 본체가 `_run_evolution_cycle_inner()`로 분리되어 있음에 주의.
