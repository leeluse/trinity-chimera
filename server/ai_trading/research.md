# Research: IS/OOS Splitter Implementation

## Current State Analysis

### Existing Files
1. `/Users/lsy/Desktop/project/trinity-chimery/ai_trading/core/backtest_manager.py` - Already exists with partial implementation
   - Has `split_data()` method but with bugs (syntax error on line 30: `<<` should be `<`)
   - Has `validation_gate()` method with correct logic
   - Has `calculate_trinity_score()` method
   - Has basic `run_backtest()` method

2. `/Users/lsy/Desktop/project/trinity-chimery/ai_trading/core/strategy_interface.py` - Abstract base class for strategies

3. `/Users/lsy/Desktop/project/trinity-chimery/ai_trading/tests/test_sandbox.py` - Existing tests for strategy sandbox

### Issues Found in backtest_manager.py
1. Line 30: `if len(recent_data) << total total_window * 24:` - Syntax error (should be `<`)
2. The split_data logic assumes hourly data which may not be flexible enough
3. Missing comprehensive IS/OOS validation workflow

## Requirements Analysis

### Task Requirements
1. **Data Splitter**: Recent 60-day window split into:
   - Train (IS): First 30 days
   - Validation (OOS): Last 30 days

2. **Validation Gate**: Reject if `oos_score < is_score * 0.7`

3. **Implementation Details**:
   - Create/modify `BacktestManager` class
   - Work with OHLCV data
   - Store IS and OOS metrics separately
   - Final Trinity Score from OOS performance
   - Add `validate_strategy()` method

## Implementation Plan

### Step 1: Write failing tests for IS/OOS splitting
### Step 2: Run tests to verify they fail
### Step 3: Implement the data splitter (fix bugs)
### Step 4: Implement validation gate
### Step 5: Run tests to verify they pass
### Step 6: Commit with proper message

## References
- ADR-006: 과적합 방지를 위해 In-Sample/Out-of-Sample 분리 및 보수적 비용 모델 적용
- PROJECT.md: Trinity Score formula

---

# Research: Why `evolution.log` is empty even though there are 4 agents

## Question Being Investigated

User observed that the `ai_trading` tmux pane shows:

```bash
if [ -f "/Users/lsy/Desktop/project/trinity-chimery/logs/evolution.log" ]; then
  tail -f "/Users/lsy/Desktop/project/trinity-chimery/logs/evolution.log"
else
  echo 'Waiting for logs...'
fi
```

The question is whether this file should contain logs when the project has 4 agents and the API server is running.

## What the Code Actually Shows

### 1. The project defines 4 agent IDs, but they are not 4 separate running daemons

The four agent identifiers are hard-coded in several places:

- `momentum_hunter`
- `mean_reverter`
- `macro_trader`
- `chaos_agent`

They appear in:

- `api/main.py` inside `scheduled_evolution_poll()`
- `api/services/self_improvement.py` in dashboard/performance helpers
- `front/lib/api.ts` as the shared frontend ID list

This means the project currently treats the 4 agents as logical identities, not as 4 independently running background services.

### 2. The API does not create `logs/evolution.log`

Search results show only one logging setup:

- `api/main.py` uses `logging.basicConfig(level=logging.INFO)`

There is no `FileHandler`, no `RotatingFileHandler`, and no code that writes to `logs/evolution.log`.

So the `ai_trading` pane is tailing a file that the current codebase does not actually populate.

### 3. The evolution loop is mostly dormant unless explicitly triggered

In `api/main.py`:

- `scheduled_evolution_poll()` iterates over the 4 agent IDs
- but it calls `run_evolution_cycle(agent_id)` without `force_trigger=True`

In `api/services/evolution_orchestrator.py`:

- `run_evolution_cycle()` immediately returns when `force_trigger` is false and the simplified trigger check leaves `is_triggered = False`

That means the scheduled hourly loop is effectively a no-op in the current implementation.

### 4. Manual evolution does produce logs, but only to stdout/stderr

The manual route:

- `POST /api/agents/{agent_id}/improve`

calls `run_evolution_cycle(..., force_trigger=True)` indirectly.

Inside the orchestrator, logging uses:

- `logger.info(...)`
- `logger.error(...)`
- `logger.exception(...)`

Those logs go to the process console by default, not to `logs/evolution.log`.

## Why the User Saw "Waiting for logs..."

The `trn` script is configured to tail:

- `/Users/lsy/Desktop/project/trinity-chimery/logs/evolution.log`

But the current backend never writes to that file.

So the expected behavior is:

- file does not exist, or
- file exists but stays empty

and the pane prints:

- `Waiting for logs...`

## Bottom Line

The answer is:

- Yes, there are 4 agent identities in the code.
- No, that does not mean there are 4 always-running services producing a shared log file.
- The current implementation logs to the API process console, not to `logs/evolution.log`.
- The scheduled evolution loop is currently mostly inactive unless manually forced.

## Practical Implication

If the goal is to see live logs in the `ai_trading` pane, the code needs one of these:

1. A real writer that appends backend logs to `logs/evolution.log`
2. A `trn` pane that tails the API process stdout instead of a file
3. A dedicated worker process that runs agent evolution and writes its own log file

## References

- `/Users/lsy/Desktop/project/trinity-chimery/api/main.py`
- `/Users/lsy/Desktop/project/trinity-chimery/api/services/evolution_orchestrator.py`
- `/Users/lsy/Desktop/project/trinity-chimery/api/services/self_improvement.py`
- `/Users/lsy/Desktop/project/trinity-chimery/api/services/evolution_trigger.py`
- `/Users/lsy/Desktop/project/trinity-chimery/front/lib/api.ts`

---

# Research: Why `ai_trading/agents/` is empty

## What Exists in the Folder Right Now

The folder contains only:

- `ai_trading/agents/CLAUDE.md`

There are no Python modules, strategy classes, or persona implementations inside `ai_trading/agents/`.

## What the Documentation Expected

The project docs still describe `agents/` as the place for:

- agent personas
- strategy generation logic
- prompt logic

See:

- `PROJECT.md` line 64
- `PROJECT.md` line 154

## What the Actual Code Uses Instead

The implemented orchestration and generation logic currently lives in `api/services/`:

- `api/services/evolution_orchestrator.py`
- `api/services/evolution_llm_client.py`
- `api/services/self_improvement.py`

The backend uses hard-coded agent IDs such as:

- `momentum_hunter`
- `mean_reverter`
- `macro_trader`
- `chaos_agent`

Those IDs are used by the API and the frontend mapping, but they are not backed by separate files in `ai_trading/agents/`.

## Likely Explanation

This looks like an architectural drift:

- the design docs anticipated a dedicated `ai_trading/agents/` module
- later work moved the orchestration into the API layer
- the `agents/` directory was left as a placeholder

So your instinct is correct:

- the code is **not** currently grouped there
- the folder is basically a planned location that has not been populated yet

## Practical Consequence

If you want the repo to match the docs, there are two cleanup paths:

1. Move persona/prompt/strategy-generation code into `ai_trading/agents/`
2. Update the docs so `api/services/` is the canonical home for agent orchestration

At the moment, the implementation is clearly in `api/services/`, not `ai_trading/agents/`.

## Migration Result

This analysis has now been acted on.

The canonical agent implementation now lives in:

- `ai_trading/agents/constants.py`
- `ai_trading/agents/trigger.py`
- `ai_trading/agents/llm_client.py`
- `ai_trading/agents/orchestrator.py`

The `api/services/` versions now serve as backward-compatible wrappers.

The repo is therefore in a transitional-but-aligned state:

- `ai_trading/agents/` is now the canonical home for agent logic
- `api/main.py` and `api/services/self_improvement.py` import from that package
- the old paths remain available so nothing else breaks immediately

---

# Research: 에이전트 페르소나 설정은 어디에 있나

## 한 줄 답

지금은 `persona.yaml`, `persona.json`, `persona.py`처럼 **페르소나만 따로 모아둔 단일 파일은 없습니다.**

페르소나 성격은 여러 파일에 나뉘어 있습니다.

- [`ai_trading/agents/constants.py`](/Users/lsy/Desktop/project/trinity-chimery/ai_trading/agents/constants.py) - 에이전트 ID 정의
- [`ai_trading/agents/llm_client.py`](/Users/lsy/Desktop/project/trinity-chimery/ai_trading/agents/llm_client.py) - LLM에게 어떤 성격으로 행동해야 하는지 알려주는 프롬프트
- [`ai_trading/agents/orchestrator.py`](/Users/lsy/Desktop/project/trinity-chimery/ai_trading/agents/orchestrator.py) - 페르소나 로직이 언제 실행될지 결정하는 상태 머신
- [`ai_trading/agents/trigger.py`](/Users/lsy/Desktop/project/trinity-chimery/ai_trading/agents/trigger.py) - 에이전트 진화 트리거 판단 로직
- [`front/lib/api.ts`](/Users/lsy/Desktop/project/trinity-chimery/front/lib/api.ts) - 프론트에서 사용하는 공통 `agent_id` 목록

## 파일별 역할

### 1. `ai_trading/agents/constants.py`

이 파일이 사실상 페르소나 목록에 가장 가깝습니다.

여기에는 다음이 들어 있습니다.

- 4개의 논리적 에이전트 ID
  - `momentum_hunter`
  - `mean_reverter`
  - `macro_trader`
  - `chaos_agent`
이 파일은 **성격 자체를 정의하지는 않고**, ID 목록만 정합니다.

### 2. `ai_trading/agents/llm_client.py`

실제 “페르소나 느낌”이 가장 강하게 드러나는 곳입니다.

`EvolutionLLMClient`의 `_assemble_c_mode_context()`가 LLM용 프롬프트를 만들고, 그 안에서 모델에게 다음을 지시합니다.

- 어떤 종류의 전략을 개선해야 하는지
- 어떤 지표를 중요하게 볼지
- 손실 구간을 어떻게 해석할지
- 어떤 제약을 지켜야 하는지
- 다음 전략 코드를 어떤 형태로 내놓아야 하는지

즉, “에이전트가 어떤 말투와 사고방식으로 움직이는가”를 보려면 이 파일이 핵심입니다.

### 3. `ai_trading/agents/orchestrator.py`

이 파일은 페르소나 로직이 **언제, 어떤 순서로** 실행될지를 제어합니다.

여기서 하는 일은:

- 진화 상태 관리
- 트리거 확인
- 현재 전략 불러오기
- 새 전략 코드 생성
- 검증
- 백테스트
- 새 버전 저장

즉, 이 파일은 **페르소나의 생명주기**를 다루지만, 페르소나의 말투 그 자체를 적는 곳은 아닙니다.

### 4. `ai_trading/agents/trigger.py`

에이전트가 진화해야 하는지 판단하는 휴리스틱이 들어 있습니다.

예를 들면:

- 국면 변화
- 성과 악화
- 경쟁 압박
- heartbeat / 최신성 신호

이것도 “성격 텍스트”는 아니지만, 페르소나가 언제 깨어나 움직일지 정하는 운영 로직입니다.

### 5. `front/lib/api.ts`

프론트엔드와 백엔드가 함께 쓰는 `agent_id` 목록이 들어 있습니다.

이제는 이름을 ID로 바꾸는 변환 단계가 없고, 화면과 API 모두 `agent_id` 기준으로 움직입니다.

## 왜 헷갈렸나

이 구조가 헷갈리는 이유는 예전에 문서와 실제 구현이 어긋나 있었기 때문입니다.

- 문서상으로는 `agents/` 안에 페르소나 코드가 있을 것처럼 보였고
- 실제 구현은 한동안 `api/services/` 쪽에 있었습니다
- 지금은 `ai_trading/agents/`로 옮겼지만, 여전히 한 파일에 다 들어 있는 구조는 아니라서 처음 보면 더 헷갈릴 수 있습니다

즉, 지금도 “각 에이전트가 어떻게 생각하는가”를 한 번에 수정하는 단일 파일은 없습니다.

## 실무적으로 어디를 고치면 되나

바꾸고 싶은 내용에 따라 파일이 다릅니다.

- 에이전트 ID 목록을 바꾸고 싶다 -> `ai_trading/agents/constants.py`
- 프롬프트 성격 / C-mode 행동을 바꾸고 싶다 -> `ai_trading/agents/llm_client.py`
- 언제 에이전트를 깨울지 바꾸고 싶다 -> `ai_trading/agents/orchestrator.py` 또는 `ai_trading/agents/trigger.py`
- 프론트에서 쓰는 ID 목록을 바꾸고 싶다 -> `front/lib/api.ts`

## 참고 파일

- `/Users/lsy/Desktop/project/trinity-chimery/ai_trading/agents/constants.py`
- `/Users/lsy/Desktop/project/trinity-chimery/ai_trading/agents/llm_client.py`
- `/Users/lsy/Desktop/project/trinity-chimery/ai_trading/agents/orchestrator.py`
- `/Users/lsy/Desktop/project/trinity-chimery/ai_trading/agents/trigger.py`
- `/Users/lsy/Desktop/project/trinity-chimery/front/lib/api.ts`

---

# Research: 원래 의도한 4단계 루프와 현재 구현의 거리

## 사용자가 의도한 핵심 루프

사용자가 명시한 이 프로젝트의 원래 취지는 다음 4단계다.

1. 백테스팅이 실시간으로 계속 돌아간다
2. 그 결과가 LLM에 전달된다
3. LLM이 전략을 수정한다
4. 대시보드에서 더 나은 에이전트 성과를 보고 사람이 좋은 전략을 찾는다

이 정의는 매우 중요하다. 현재 코드베이스에서 빠진 핵심도 결국 이 4단계가 완전한 루프로 닫혀 있지 않다는 데 있다.

## 현재 구현과 비교한 결론

현재 시스템은 이 루프를 "완전히 구현한 시스템"이 아니라, "루프의 뼈대가 있는 프로토타입"에 가깝다.

상태를 한 줄씩 보면 다음과 같다.

### 1. 백테스팅이 실시간으로 계속 돌아가는가

부분적으로만 그렇다.

- `api/main.py`에는 APScheduler 기반 `scheduled_evolution_poll()`가 있다
- 하지만 `ai_trading/agents/orchestrator.py`의 `run_evolution_cycle()` 안에서
  `force_trigger=False`일 때 `is_triggered = False`로 바로 return 한다

즉:

- 스케줄러 틀은 있다
- 하지만 실질적인 자율 진화 루프는 현재 사실상 비활성이다

따라서 사용자가 의도한 "계속 돌아가는 루프"와는 아직 거리가 있다.

### 2. 백테스트 결과가 LLM에 전달되는가

형식적으로는 그렇지만, 실제 데이터 연결은 약하다.

`EvolutionOrchestrator`는 `evolution_package`를 만들어 `EvolutionLLMClient`로 넘긴다.
하지만 지금 패키지 내부 값은 상당수가 하드코딩 또는 mock 성격이다.

예를 들면:

- `trinity_score`: 고정값
- `return`, `sharpe`, `mdd`: 고정값
- `market_regime`: `"Bull"`
- `competitive_rank`: `"5th"`
- `loss_period_logs`: 정적 문자열

즉:

- "LLM에게 결과를 전달하는 구조"는 있다
- 하지만 "실제 최신 백테스트 결과를 정확히 전달하는 구조"는 아직 미완성이다

### 3. LLM이 전략을 수정하는가

구조는 있으나, 아직 완전한 실전 모드는 아니다.

`ai_trading/agents/llm_client.py`는:

- C-mode 프롬프트를 만든다
- LLM 호출 인터페이스를 가진다
- 생성 코드에 대해 self-correction 루프를 돈다

하지만 현재는:

- 실제 LLM 서비스가 없으면 mock 전략 코드를 반환한다
- 따라서 조용히 "가짜 성공"처럼 보일 위험이 있다

즉:

- 전략 수정 엔진의 외형은 있다
- 하지만 "실제 전략 진화 시스템"으로 믿기엔 아직 안전장치와 실패 처리 정의가 부족하다

### 4. 대시보드에서 더 나은 전략을 사람이 찾을 수 있는가

부분적으로만 가능하다.

프론트는 다음을 보여줄 기반을 이미 갖고 있다.

- 에이전트별 성과 데이터
- 시계열
- 대시보드 메트릭

하지만 아직 부족한 부분은 명확하다.

- 전략 버전별 비교가 약하다
- 어떤 진화가 실제 점수 개선을 만들었는지 추적성이 부족하다
- `logs/evolution.log` 같은 운영 로그 파일도 현재 자동 생성되지 않는다

즉:

- "보여주는 화면"은 있다
- 하지만 "좋은 전략을 빠르게 고르게 해주는 운영 대시보드"까지는 아직 아니다

## 핵심 해석

이 프로젝트의 진짜 core는 "페르소나 4개"가 아니다.

진짜 core는 다음 루프다.

```text
실행 가능한 전략 후보 생성
-> 빠른 백테스트
-> OOS/비용/리스크 게이트
-> 통과한 전략만 저장
-> 성과를 시각화
-> 다시 다음 후보 생성
```

즉, 사용자가 말한 4단계는 조금 더 실무적으로 풀면:

```text
실시간 또는 주기적 평가
-> 평가 결과를 LLM 컨텍스트에 반영
-> 전략 수정 및 새 후보 생성
-> 대시보드에서 비교/선별
-> 다시 루프 반복
```

현재 빠진 핵심은 "이 루프가 정말 닫혀 있느냐"이다.

## 그래서 무엇을 우선해야 하나

사용자 의도에 가장 가깝게 만들려면 우선순위는 다음 순서가 맞다.

1. 자율 트리거를 실제로 작동시키기
2. 백테스트 결과를 mock이 아닌 실제 평가값으로 LLM에 넣기
3. LLM 실패 시 조용한 fallback 대신 명시적 실패 처리로 바꾸기
4. 전략 승격/거부 결과를 구조화 로그와 버전 이력으로 남기기
5. 대시보드에서 "어느 진화가 실제로 좋아졌는지" 보이게 하기

이 순서가 중요한 이유는:

- 먼저 루프가 돌아야 하고
- 그다음 루프 품질을 높여야 하며
- 마지막에 사람이 더 잘 고를 수 있게 보여줘야 하기 때문이다

## PROJECT.md에 반영되어야 할 관점

`PROJECT.md`는 앞으로 다음 관점으로 더 가까워져야 한다.

- 프로젝트의 핵심은 "전략 자동 발견 루프"라고 초반에 못 박기
- 4개 페르소나는 부차적 설명으로 내리고, 루프를 전면에 올리기
- Gap Analysis를 "루프가 왜 아직 안 닫혔는가" 중심으로 재정리하기
- P0는 반드시 "실제 자율 루프 작동"에만 집중시키기
- 대시보드는 "예쁜 화면"이 아니라 "좋은 전략 선별 도구"로 정의하기

## 참고 파일

- `/Users/lsy/Desktop/project/trinity-chimery/api/main.py`
- `/Users/lsy/Desktop/project/trinity-chimery/ai_trading/agents/orchestrator.py`
- `/Users/lsy/Desktop/project/trinity-chimery/ai_trading/agents/llm_client.py`
- `/Users/lsy/Desktop/project/trinity-chimery/ai_trading/core/backtest_manager.py`
- `/Users/lsy/Desktop/project/trinity-chimery/front/lib/api.ts`

---

# 연구: IS/OOS 분할기(Splitter) 구현

## 현재 상태 분석

### 기존 파일
1. `ai_trading/core/backtest_manager.py` - 일부 구현된 상태로 존재
   - `split_data()` 메서드가 있으나 버그 있음 (30행 구문 오류: `<<`를 `<`로 수정 필요)
   - `validation_gate()` 메서드는 올바른 로직으로 구현됨
   - `calculate_trinity_score()` 메서드 보유
   - 기본적인 `run_backtest()` 메서드 보유

2. `ai_trading/core/strategy_interface.py` - 전략을 위한 추상 베이스 클래스

3. `ai_trading/tests/test_sandbox.py` - 전략 샌드박스를 위한 기존 테스트

### backtest_manager.py에서 발견된 문제점
1. 30행: `if len(recent_data) << total total_window * 24:` - 구문 오류 (`<` 여야 함)
2. `split_data` 로직이 시간 단위(hourly) 데이터만 가정하고 있어 유연성이 부족함
3. 포괄적인 IS/OOS 검증 워크플로우가 누락됨

## 요구사항 분석

### 작업 요구사항
1. **데이터 분할기(Data Splitter)**: 최근 60일의 윈도우를 다음과 같이 분할:
   - 훈련 (IS): 처음 30일
   - 검증 (OOS): 마지막 30일

2. **검증 게이트(Validation Gate)**: `oos_score < is_score * 0.7` 인 경우 거절(Reject)

3. **구현 세부사항**:
   - `BacktestManager` 클래스 생성/수정
   - OHLCV 데이터와 호환
   - IS 및 OOS 메트릭을 별도로 저장
   - 최종 트리니티 점수는 OOS 성과를 기준으로 산출
   - `validate_strategy()` 메서드 추가

## 구현 계획

### 1단계: IS/OOS 분할에 대한 실패하는 테스트 작성
### 2단계: 테스트 실행 및 실패 확인
### 3단계: 데이터 분할기 구현 (버그 수정)
### 4단계: 검증 게이트 구현
### 5단계: 테스트 실행 및 통과 확인
### 6단계: 적절한 메시지와 함께 커밋

## 참고 문서
- ADR-006: 과적합 방지를 위해 In-Sample/Out-of-Sample 분리 및 보수적 비용 모델 적용
- PROJECT.md: Trinity Score 공식
