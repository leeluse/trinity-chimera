# LLM Arbiter 시스템

## 개요

LLM Arbiter는 Claude API를 활용한 지능형 자본 할당 및 전략 최적화 시스템입니다.

## 구성 컴포넌트

### 1. LLMArbiter (`llm_arbiter.py`)

**목적:** 에이전트 성과를 분석하고 LLM을 통해 자본을 재배분

**핵심 클래스:**
- `LLMArbiter`: 메인 오케스트레이터
- `AgentPerformance`: 에이전트 성과 메트릭
- `AllocationDecision`: 배분 결정

**재배분 규칙:**
```
최소 배분: 5% (min_allocation)
최대 배분: 50% (max_allocation)
과적합 패널티: overfit_score > 0.3 → 10% 감소
강제 축소: Sharpe < -0.5 for 7d → 5%로 조정
```

**사용 예시:**
```python
from ai_trading.arbiter import LLMArbiter, AgentPerformance

arbiter = LLMArbiter(model="claude-sonnet-4-6")

performances = [
    AgentPerformance(
        name="momentum_hunter",
        sharpe_7d=1.2,
        max_drawdown=0.08,
        win_rate=0.65,
        avg_hold_bars=12.5,
        regime_fit=0.85,
        diversity_score=0.45,
        overfit_score=0.15,
        current_allocation=0.30,
    )
]

decision = await arbiter.analyze_performance(performances, "bull")
print(f"New allocation: {decision.allocations}")
print(f"Confidence: {decision.confidence}")
```

### 2. StrategyGenerator (`strategy_generator.py`)

**목적:** 에이전트 자가 전략 생성 및 파라미터 최적화

**핵심 클래스:**
- `StrategyGenerator`: 전략 생성 엔진
- `StrategyProposal`: 파라미터 제안
- `ValidationOutcome`: 검증 결과

**자가 개선 사이클:**
```
매 14일:
1. LLM에 파라미터 조정 요청
2. 제안된 파라미터로 30일 백테스트
3. Sharpe 개선 >= 0.1 확인
4. 채택시 파라미터 업데이트
5. Arbiter에 변경 통보
```

**기본 페르소나:**
```python
DEFAULT_PERSONAS = {
    "momentum_hunter": "Trend-following, bull regime specialist",
    "mean_reverter": "Mean reversion, sideways/bear specialist",
    "macro_trader": "Big picture, regime-aware, low frequency",
    "chaos_agent": "Contrarian, diversity keeper",
}
```

### 3. MarketAnalyzer (`market_analyzer.py`)

**목적:** 실시간 시장 분석 및 리스크 모니터링

**핵심 클래스:**
- `MarketAnalyzer`: 종합 분석기
- `VolatilityCalculator`: 변동성 계산
- `CorrelationTracker`: 에이전트 상관관계 추적

**분석 항목:**
- 시장 레짐 (bull/sideways/bear)
- 변동성 (short/medium/long term)
- 추세 강도
- 리스크 신호
- 에이전트 상관관계

### 4. Arena 통합

**통합 포인트:**
```python
arena = Arena(agents=agents, enable_llm_arbiter=True)

# LLM 기반 재배분 실행
result = await arena.run_llm_rebalance(
    current_regime="bull",
    market_context={"volatility": 0.25}
)
```

## 환경 변수

```bash
# 필수
ANTHROPIC_API_KEY=sk-...

# 선택
LLM_ARBITER_MODEL=claude-sonnet-4-6
LLM_ARBITER_MAX_TOKENS=4096
LLM_ARBITER_TEMPERATURE=0.2
```

## 파일 구조

```
ai_trading/arbiter/
├── __init__.py
├── llm_arbiter.py       # LLM Arbiter Core
├── strategy_generator.py # 자가 전략 생성
├── market_analyzer.py   # 시장 분석
└── CLAUDE.md           # 이 파일
```

## 테스트

```bash
pytest ai_trading/tests/test_llm_arbiter.py -v
```

## 주의사항

1. **API 비용:** LLM 호출은 비용이 발생하므로 주기를 적절히 설정
2. **타임아웃:** 비동기 호출 적절히 처리
3. **폴백:** API 실패시 equal allocation으로 폴백
4. **제약:** min/max allocation 반드시 적용
