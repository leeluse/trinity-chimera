# Evolution System

## 핵심 컴포넌트
- Orchestrator: `server/modules/evolution/orchestrator.py`
- Trigger: `server/modules/evolution/trigger.py`
- State Manager: `server/modules/evolution/agents.py`
- Evolution Backtest: `server/modules/backtest/evolution/evolution_engine.py`

## 실행 단계
1. 트리거 조건 확인
2. 현재 전략 로딩(Supabase)
3. LLM 코드 생성
4. 후보 코드 검증(백테스트)
5. 점수 비교 후 채택/거절
6. 상태를 IDLE로 복귀

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

## 주의 포인트
- `router.py`에서 `force_trigger` 인자를 사용하는 호출이 있으며, 오케스트레이터 함수 시그니처(`force`)와 동기화 확인 필요.
