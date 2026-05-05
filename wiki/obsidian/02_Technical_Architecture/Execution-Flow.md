# Execution Flow

## A. 수동 진화 루프
1. UI에서 RUN LOOP 클릭
2. `POST /api/agents/run-loop`
3. 에이전트 목록 큐잉
4. 순차 진화 실행
5. 이벤트/스냅샷 폴링으로 UI 반영

## B. 자동 진화 루프
1. `/api/system/automation` enabled=true
2. scheduler가 주기적으로 poll job 실행
3. 각 agent에 대해 `run_evolution_cycle` 호출
4. 성공/실패 이벤트 누적

## C. 채팅 전략 생성
1. `POST /api/chat/run` (SSE)
2. stage1 의도/추론
3. stage2 설계 표 생성
4. stage3 코드 생성
5. stage4 백테스트
6. stage5(마이닝 모드) 품질 판정/저장

## D. 백테스트 워크벤치
1. 전략 목록 로드 `/api/backtest/strategies`
2. 전략 코드 조회 `/api/backtest/strategies/{key}/code`
3. 실행 `/api/backtest/run`
4. 차트/거래/지표 렌더링
