# Evolution System

> **Last Updated**: 2026-05-11
> **현재 상태**: ⚠️ 비활성화 — 코드는 존재하나 서버에 연결되지 않음

---

## 1. 현황 요약

| 항목 | 상태 |
|---|---|
| `main.py` evolution 라우터 등록 | ❌ 미등록 (`/api/agents/...` 없음) |
| APScheduler 자율 루프 | ❌ 없음 |
| 채팅 `INTENT_EVOLVE` 감지 시 동작 | ⚠️ `run_create_pipeline(is_mining=True)` — 일반 전략 생성과 동일 |
| Evolution Wiki Memory 기록 | ❌ 루프 없으므로 기록 미누적 |
| `/api/agents/...` 엔드포인트 | ❌ 응답 없음 (라우터 미포함) |

**결론**: 에볼루션 모듈 코드(`server/modules/evolution/`)는 존재하나 현재 아무 곳에도 연결되어 있지 않습니다.  
채팅에서 "에볼루션 채굴" 인텐트가 감지되어도 내부적으로 `is_mining=True` 플래그를 넘기는 **일반 전략 생성 파이프라인**으로 처리됩니다.

---

## 2. 코드 위치 (참조용)

```
server/modules/evolution/
├── router.py            # APIRouter (main.py에 미등록)
├── orchestrator.py      # EvolutionOrchestrator (미호출)
├── self_improvement.py  # SelfImprovementService (미호출)
├── scoring.py           # calculate_trinity_score (engine/router.py에서 사용)
├── constants.py         # AGENT_IDS, ACTIVE_AGENT_IDS
└── wiki_memory.py       # EvolutionWikiMemory (루프 없으므로 비활성)

wiki/obsidian/03_Backend/Evolution-Memory/
├── Strategy-Constitution.md   # 채택 기준 JSON (파싱 코드 있음)
├── Experiment-Ledger.md       # 실험 이력 (비어 있음 — 2026-05-10 초기화)
├── Failure-Patterns.md        # 실패 패턴 (비어 있음 — 2026-05-10 초기화)
├── Accepted-Strategies.md     # 채택 전략 (없음)
└── state.json                 # 런타임 상태 (초기화됨)
```

---

## 3. 재활성화 방법 (메모)

다시 활성화하려면 아래 두 가지가 필요합니다:

**① `main.py`에 라우터 등록**
```python
from server.modules.evolution.router import router as evolution_router, dashboard_router
app.include_router(evolution_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
```

**② APScheduler에 루프 등록 (선택)**
```python
# startup_event() 안에 추가
from server.modules.evolution.orchestrator import get_evolution_orchestrator
evo = get_evolution_orchestrator()
scheduler.add_job(
    lambda: asyncio.create_task(evo.run_evolution_cycle("momentum_hunter")),
    "interval", minutes=30, id="evo_loop", coalesce=True, max_instances=1,
)
```

---

## 4. Strategy Constitution (채택 기준 — 코드 내 기본값)

`Strategy-Constitution.md` 내 JSON 블록이 런타임에 파싱됩니다. 파일이 없거나 파싱 실패 시 아래 기본값으로 동작합니다.

```json
{
  "hard_gates": {
    "min_win_rate": 0.35,
    "min_profit_factor": 1.05,
    "min_total_return": -0.10,
    "max_drawdown": 0.35,
    "min_total_trades": 15,
    "min_sharpe_ratio": -0.10
  },
  "quick_gates": {
    "min_win_rate": 0.30,
    "min_profit_factor": 1.01,
    "min_total_return": -0.20,
    "max_drawdown": 0.40,
    "min_total_trades": 8,
    "min_sharpe_ratio": -0.50
  },
  "budgets": {
    "max_candidates_per_cycle": 2,
    "max_llm_calls_per_cycle": 2
  },
  "memory": {
    "recent_failures_for_prompt": 5,
    "recent_successes_for_prompt": 3,
    "dedupe_window": 120
  }
}
```

---

## 5. scoring.py — 현재 사용 중인 부분

`server/modules/evolution/scoring.py`의 `calculate_trinity_score`는 **에볼루션 루프와 무관하게** `engine/router.py` 리더보드에서 호출됩니다.

```python
# engine/router.py
from server.modules.evolution.scoring import calculate_trinity_score
```

이 함수는 현재 정상 작동 중입니다.
