# Evolution Memory Workflow

## 목적
반복 저품질/중복 전략을 자동 차단하고, 실패/성공 패턴을 다음 생성 프롬프트에 주입해 진화 효율을 높인다.

## 저장 위치
- `wiki/obsidian/03_Backend/Evolution-Memory/Strategy-Constitution.md`
- `wiki/obsidian/03_Backend/Evolution-Memory/Failure-Patterns.md`
- `wiki/obsidian/03_Backend/Evolution-Memory/Experiment-Ledger.md`
- `wiki/obsidian/03_Backend/Evolution-Memory/Accepted-Strategies.md`
- `wiki/obsidian/03_Backend/Evolution-Memory/state.json`

## 실행 순서
1. 후보 생성
2. 코드 fingerprint 중복 검사
3. 정적 검증(AST/security)
4. Quick Gate 백테스트(저비용)
5. Full Gate 백테스트(고신뢰)
6. Hard Gate + OOS 개선 판정
7. 채택/거절 결과를 위키에 기록

## 적용 범위
- 4개 에이전트 자동 진화 루프 (`/api/agents/run-loop`)
- 채팅 기반 전략 생성 파이프라인 (`/api/chat/run`)

두 경로 모두 Obsidian 메모리(Constitution/Failure/Ledger)를 읽고, 실행 결과를 다시 기록합니다.

## 운영 튜닝
`Strategy-Constitution.md` JSON 블록에서 조절:
- `hard_gates`
- `quick_gates`
- `budgets`
- `memory`
