# Recent Changes (2026-04)

## 2026-04-18 Chat Pipeline 전면 재설계 + 모델 역할 라우팅

### 인텐트 분류기 전면 교체
| Before | After |
|---|---|
| `"전략" in text` — substring 오탐 다발 | `_classify_intent()` — 맥락 패턴 매칭 (동사+명사 쌍) |
| "전략적으로 생각해봐" → 파이프라인 트리거 ❌ | GENERAL_CHAT으로 올바르게 분류 ✅ |
| `"응" in text` → 응급도 승인 ❌ | 짧은 토큰 정확 매칭으로 오탐 방지 ✅ |

### 전략 수정 파이프라인 신설 (STRATEGY_MODIFY)
- "방금 만든 전략 고쳐줘" 등 → MODIFY 인텐트 감지
- Stage 1: 이전 전략 약점 분석 (`MODIFY_ANALYZE_TEMPLATE`)
- Stage 2: 수정 설계도
- Stage 3: 수정된 코드 (`MODIFY_CODE_TEMPLATE`) — 파라미터만 변경 금지
- Stage 4: 수정 전후 비교표 (수익률/MDD/Sharpe/거래 수)

### 세션 메모리 도입
- `_session_last_strategy[session_id]` — 백테스트 성공 시마다 업데이트
- MODIFY 파이프라인이 이전 코드+성과를 자동 로드

### 구조 리팩터링
- `execute_pipeline()` → 분류기 + 확인 라우터
- `_execute_general_chat()` — 일반 대화
- `_execute_create_pipeline()` — 생성/채굴
- `_execute_modify_pipeline()` — 수정
- `_run_and_yield_backtest()` — 공통 백테스트 실행기
- `_run_mining_backtest()` — WFO+Monte Carlo 전용

### evaluate_improvement 버그 수정
- baseline trades=0 (빈 전략) → trinity_score=25 (MDD 만점) → 모든 후보 탈락 버그
- 수정: `baseline_trades == 0`이면 후보가 거래만 해도 채택

### 모델 역할 라우팅
| 역할 | 모델 |
|---|---|
| 메인 브레인 (Stage 1) | `qwen3.5-122b-a10b` |
| 장문 분석 (Stage 2 + Evolution) | `kimi-k2.5` |
| 코더 (Stage 3) | `deepseek-v3.1-terminus` |
| 빠른 응답 (Tips) | `minimax-m2.5` |

### 영향 파일
- `server/modules/chat/handler.py` — 전면 재작성
- `server/modules/chat/prompts.py` — MODIFY_ANALYZE_TEMPLATE, MODIFY_CODE_TEMPLATE 추가
- `server/modules/evolution/scoring.py` — evaluate_improvement 버그 수정
- `server/shared/llm/client.py` — stream_analysis_reply, stream_quick_reply 추가
- `.env` — 4개 모델 역할 env 정의

### 신규 위키 문서
- [[Chat-Pipeline]] — 채팅 파이프라인 설계 전체
- [[LLM-Model-Roles]] — 역할별 모델 라우팅

---

## 2026-04-17 파이프라인 강화 (Evolution + Chat)

### P1 버그 수정
| 항목 | 내용 |
|---|---|
| per-agent async Lock | 동일 에이전트 동시 실행 → 중복 후보 폭탄 방지 |
| LLM Circuit Breaker | 연속 5회 실패 시 300초 자동 대기 후 재개 |
| LLM 프롬프트 부정지시 제거 | `StrategyInterface 사용 금지` → `Strategy, Signal import 명시` |

### 전략 코드 생성 규격 통일
- 진화·채팅 파이프라인 모두 `generate_signal(train_df, test_df) → pd.Series` 함수 방식으로 통일
- 클래스 기반(행별 루프, 2순위 경로) 대신 벡터화 함수(1순위 경로) 사용
- LLM 프롬프트에 데이터 스키마·지표 레시피·작동 예시 추가
- `ta`, `talib`, `scipy` 금지 명시
- 최소 거래 수 요건 강화 (20~30건 이상)

### 영향 파일
- `server/modules/evolution/llm.py` — 프롬프트 전면 재작성
- `server/modules/evolution/orchestrator.py` — Lock + Circuit Breaker 추가
- `server/modules/chat/prompts.py` — CODE_PROMPT_TEMPLATE, MINING_PROMPT_TEMPLATE 강화

### 신규 위키 문서
- [[Strategy-Code-Spec]] — 전략 코드 규격 단일 진실 출처(SSoT)

---

## 2026-04-16 이전 변경 흐름

- 대시보드/백테스트 UI 고도화
- 하이브리드 전략 엔진 고도화
- 진화 로그 패널 및 운영 UX 개선
- 네트워크/터널 연동 안정화 작업
- `run public` 경로 강화
- API 타임아웃/폴백 정책 조정
- 전략 로딩 호환 계층 보강

## 위키 반영 기준
본 위키는 2026-04-17 기준 코드를 바탕으로 재구성됨.
