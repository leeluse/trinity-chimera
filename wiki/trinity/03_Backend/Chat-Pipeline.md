# Chat Pipeline

채팅 인터페이스를 통한 전략 생성·수정·진화 파이프라인 전체 설계.

## 아키텍처 개요

```
사용자 메시지
     │
     ▼
_classify_intent()      ← 인텐트 분류기 (5가지)
     │
     ├─ GENERAL_CHAT   → 일반 대화 (Stage 1만, 확인 없이 즉시)
     ├─ STRATEGY_CREATE → 전략 생성 확인 → 4단계 파이프라인
     ├─ STRATEGY_MODIFY → 수정 확인 → 분석+수정+비교 파이프라인
     ├─ STRATEGY_EVOLVE → 채굴 확인 → WFO+Monte Carlo 파이프라인
     └─ STRATEGY_BACKTEST → 백테스트 확인 → 직접 재실행
```

## 인텐트 분류 규칙

`_classify_intent()` — 맥락 패턴 매칭 (단순 substring 금지)

| 인텐트 | 감지 조건 | 예시 |
|---|---|---|
| EVOLVE | `에볼루션\|채굴\|마이닝\|evolution\|mining` | "에볼루션 돌려줘" |
| MODIFY | 수정 동사 + (전략 명사 or 이전 참조) | "방금 만든 전략 고쳐줘" / "코드 수정해줘" |
| BACKTEST | `백테스트\|backtest` (생성 동사 없음) | "백테스트 해줘" |
| CREATE | 생성 동사 + 전략 명사 | "EMA 전략 짜줘" / "새 전략 만들어줘" |
| GENERAL | 그 외 | "안녕" / "RSI가 뭐야?" / "전략적으로 생각해봐" |

### 핵심 설계 원칙
- **"전략"** 단어만으로는 트리거되지 않는다. (오탐 방지)
- 짧은 승인 토큰(`예`, `응`, `ㄱ`)은 **정확 매칭** (부분 문자열 금지 → "응급" 오탐 방지)
- 확인 요청 후 yes/no가 아닌 새 메시지가 오면 대기를 취소하고 재분류

## 파이프라인별 단계

### A. 전략 생성 (`_execute_create_pipeline`)

| Stage | 모델 | 역할 |
|---|---|---|
| 1 추론 | `qwen3.5-122b-a10b` (메인 브레인) | 사용자 의도 분석, 전략 방향 도출 |
| 2 설계 | `kimi-k2.5` (장문 분석) | 진입/청산/필터 설계도 마크다운 표 |
| 3 코드 | `deepseek-v3.1-terminus` (코더) | `generate_signal()` Python 코드 생성 |
| 4 백테스트 | ChatBacktester | 경량 백테스트 → 게이트 평가 → Tips |

### B. 전략 수정 (`_execute_modify_pipeline`)

| Stage | 역할 |
|---|---|
| 1 분석 | 이전 전략 코드 + 성과 → 약점 진단 (`MODIFY_ANALYZE_TEMPLATE`) |
| 2 설계 | 수정 방향 설계도 |
| 3 코드 | 수정된 코드 (`MODIFY_CODE_TEMPLATE`) — 파라미터만 바꾸면 거부 |
| 4 비교 | 수정 전후 성과 비교표 (수익률/MDD/Sharpe/거래 수) |

수정 파이프라인 선행 조건: `_session_last_strategy[session_id]`에 이전 전략 존재.

### C. 에볼루션 채굴 (`_execute_create_pipeline(is_mining=True)`)

1. 랜덤 페르소나 + 크로스도메인 씨드 선택
2. `MINING_PROMPT_TEMPLATE` 로 Stage 1 실행
3. 일반 파이프라인과 동일하게 Stage 2-3 진행
4. **Stage 4**: `BacktestEngine.run_full_validation()` (WFO + Monte Carlo)
5. Trinity Score 계산 → `is_robust`이면 금고(DB) 저장

## 세션 메모리

```python
_session_last_strategy: Dict[str, Dict] = {}
# {session_id: {code, title, metrics, gate_metrics, timestamp}}
```

- 백테스트 성공 시마다 자동 업데이트
- MODIFY 파이프라인이 이 데이터를 읽어 이전 전략 이해
- 세션 종료 시 소멸 (영속성 없음 — 향후 DB 연동 예정)

## 코드 검증 흐름

```
LLM 코드 출력
    │
    ├─ extract_python_code() — ```python 블록 추출
    ├─ StrategyLoader.validate_code() — AST 보안 검사 (os/eval/exec 등)
    ├─ memory.is_duplicate() — 중복 fingerprint 확인
    └─ 통과 시 → 백테스트 실행
```

## 파일 매핑

| 파일 | 역할 |
|---|---|
| `server/modules/chat/handler.py` | 인텐트 분류기, 파이프라인 라우터, 각 파이프라인 구현 |
| `server/modules/chat/prompts.py` | 모든 프롬프트 템플릿 (MODIFY_ANALYZE, MODIFY_CODE 포함) |
| `server/shared/llm/client.py` | 역할별 LLM 호출 함수 (stream_analysis_reply 등) |
| `server/modules/evolution/scoring.py` | 하드게이트 평가, evaluate_improvement |
| `server/modules/backtest/chat/chat_backtester.py` | 경량 백테스트 실행기 |

## 관련 문서

- [[Strategy-Code-Spec]] — 코드 생성 규격
- [[Evolution-System]] — 자율 진화 루프
- [[LLM-Model-Roles]] — 역할별 모델 라우팅
