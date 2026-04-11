# Trinity v2.0 Risk Model - 개선안 (백테스팅 중심)

> **범위 변경**: 실시간 실행 → 백테스팅 기반 전략 평가로 조정

## 1. 문제 인식 (ai_expert 피드백 반영)

### 기존 설계 (v2.0-실시간 중심)의 문제점
- **Latency Budgets**: 실시간 실행을 위한 <10ms 리스크 체크는 백테스팅 시스템에서 과도함
- **Execution Prevalidation**: 주문장(Order Book) 분석은 v2.0 범위 외
- **Time Decay**: 실시간 신호 감쇠는 백테스팅에 적용 불가

### v2.0 방향성 정립
**핵심 목표**: LLM이 전략을 발전시켜 높은 Sharpe/Win Rate의 최고 전략 발견
- 백테스팅 환경에서의 리스크 관리
- 전략 비교를 위한 정량적 Risk-Adjusted Metric
- IS/OOS 검증에서의 과적합 방지

---

## 2. 개선된 v2.0 Risk Model

### 2.1 백테스팅 중심 Risk Layer

```python
class BacktestRiskEvaluator:
    """
    백테스팅 결과에 대한 리스크 평가
    실시간 실행이 아닌, 전략 자체의 견고성 평가
    """

    def evaluate_strategy(self, backtest_result: BacktestMetrics) -> RiskReport:
        checks = {
            'sharpe_sufficiency': backtest_result.sharpe > MIN_SHARPE_THRESHOLD,
            'drawdown_tolerance': backtest_result.max_drawdown > MAX_DD_THRESHOLD,
            'win_rate_minimum': backtest_result.win_rate > MIN_WIN_RATE,
            'profit_factor': backtest_result.profit_factor > MIN_PROFIT_FACTOR,
            'trade_count_sufficiency': backtest_result.trade_count > MIN_TRADES,
        }
        return RiskReport(passed=checks, score=self.calculate_risk_score(checks))

    def calculate_risk_score(self, metrics: BacktestMetrics) -> float:
        """
        종합 Risk-Adjusted Score
        - Kelly Criterion 기반 적정 포지션 사이즈 반영
        - Conservative Cost Model 적용
        """
        kelly_fraction = self.kelly_criterion(
            win_rate=metrics.win_rate,
            avg_win=metrics.avg_win,
            avg_loss=metrics.avg_loss
        )

        # Conservative adjustment: Half Kelly for robustness
        position_size = kelly_fraction * 0.5

        # Cost-adjusted return
        cost_adjusted_return = self.apply_conservative_costs(
            gross_return=metrics.gross_return,
            trade_count=metrics.trade_count,
            fee_per_trade=0.0005,  # 5bps
            slippage_factor=1.5    # Conservative multiplier
        )

        return self.combine_metrics(cost_adjusted_return, position_size, metrics.sharpe)
```

### 2.2 기존 ai_expert 초안의 유효한 부분 채택

**✅ 채택할 설계 (백테스팅에 적용 가능)**

```python
@risk_guardrail
def validate_backtest(signal: AISignal, backtest_metrics: BacktestMetrics) -> RiskDecision:
    # 1. RAG Pattern Matching (overfitting 방지)
    historical_regime_match = rag_retriever.get_similar_regimes(signal.regime)
    if historical_regime_match.sr_score < 0.6:
        return RiskWarning("low_regime_confidence: 높은 Sharpe가 단기 이상 현상일 가능성")

    # 2. Anti-pattern Detection
    known_failure_patterns = [
        Pattern.GRID_TRADE_CHOP,       # 횡보장에서 망하는 전략
        Pattern.MOMENTUM_LAG,            # 추세 전환 늦게 반응
        Pattern.HIGH_FREQUENCY_NOISE,    # 과도한 거래
    ]

    for pattern in known_failure_patterns:
        if pattern.matches(signature=backtest_metrics.trade_signature):
            return RiskBlock(f"antipattern_detected: {pattern.name}")

    # 3. Confidence-based Evaluation
    # High confidence = OOS score > IS score * 0.7 (validation_gate 충족)
    is_confidence = backtest_metrics.is_score / backtest_metrics.oos_score
    if is_confidence < 0.7:
        return RiskBlock("overfitting_detected")

    return RiskValidated(
        adjusted_score=self.apply_risk_adjustment(backtest_metrics),
        execution_params={
            'position_size_fraction': self.optimal_f(backtest_metrics),
            'regime_confidence': is_confidence,
        }
    )
```

### 2.3 폐기된 설계 (실시간 중심)

**❌ v2.0에서 제외**

| 항목 | 제외 이유 |
|------|-----------|
| Execution Prevalidation (Liquidity Check) | 실시간 실행 없음 |
| Time Decay (Signal age) | 백테스팅은 과거 데이터 사용 |
| Smart Order Router | v3.0 범위 |
| Fill Confirmation Delay | 백테스팅은 즉시 체결 가정 |

---

## 3. ai_expert 피드백 반영 개선사항

### 3.1 RAG Integration (ai_expert 제안)

**개선 전 (기존)**
```python
# 단순 Trinity Score 비교
if new_score > old_score:
    accept_strategy()
```

**개선 후 (RAG 기반)**
```python
class RAGValidator:
    def validate_strategy_robustness(self, strategy_code: str, metrics: Metrics) -> ValidationResult:
        # 과거 유사 전략 검색
        similar_strategies = self.vector_search(
            query=strategy_code,
            filter={'regime': current_regime, 'timeframe': timeframe}
        )

        # 유사 전략들의 OOS 성과 확인
        historical_oob_scores = [s.oos_score for s in similar_strategies]
        avg_historical_oob = mean(historical_oob_scores)

        # 현재 전략이 과거 패턴보다 낮으면 경고
        if metrics.oos_score < avg_historical_oob * 0.8:
            return ValidationResult(
                passed=False,
                reason=f"Current OOS ({metrics.oos_score:.2f}) < Historical avg ({avg_historical_oob:.2f})"
            )

        return ValidationResult(passed=True)
```

### 3.2 Conservative Cost Model (ai_expert + trader 결합)

**핵심 개선**: ai_expert의 "Anti-pattern" 감지 + trader의 "Cost-adjusted Metrics"

```python
class ConservativeCostModel:
    """
    항상 실제보다 보수적인 비용 모델 적용
    """

    # ai_expert 제안: Anti-pattern 감지에서 자동 적용
    CONSERVATIVE_MULTIPLIERS = {
        'slippage': 2.0,      # 예상 슬리피지의 2배
        'fee': 1.5,           # 공시 수수료의 1.5배
        'spread': 1.3,        # 예상 스프레드의 1.3배
    }

    def calculate_trinity_score_conservative(
        self,
        gross_return: float,
        sharpe: float,
        mdd: float,
        trade_metrics: TradeMetrics
    ) -> float:
        # 기본 점수
        base_score = (gross_return * 0.4) + (sharpe * 25 * 0.35) + ((1 + mdd) * 100 * 0.25)

        # 비용 조정 (ai_expert anti-pattern: "과도한 거래 빈도")
        adjusted_return = gross_return - self.total_costs(trade_metrics)

        # MDD 보수적 조정 (ai_expert: 과거 실패 패턴 기반)
        conservative_mdd = min(mdd * 1.2, -0.35)  # MDD 항상 20% 악화 가정

        return (adjusted_return * 0.45) + (sharpe * 20 * 0.35) + ((1 + conservative_mdd) * 100 * 0.20)

    def total_costs(self, trade_metrics: TradeMetrics) -> float:
        """보수적 비용 계산"""
        base_fee = trade_metrics.trade_count * 0.0005 * self.CONSERVATIVE_MULTIPLIERS['fee']
        slippage = trade_metrics.avg_slippage * self.CONSERVATIVE_MULTIPLIERS['slippage']
        spread_cost = trade_metrics.avg_spread * self.CONSERVATIVE_MULTIPLIERS['spread']

        return base_fee + slippage + spread_cost
```

### 3.3 포트폴리오 히트 모델 (Multi-agent Risk)

```python
class PortfolioHeatAggregator:
    """
    여러 에이전트 전략의 동시 실행 리스크 평가
    """

    def calculate_portfolio_heat(
        self,
        active_strategies: List[Strategy],
        correlation_threshold: float = 0.7
    ) -> HeatReport:

        # 상관관계 배열
        correlation_matrix = self.calculate_correlations(active_strategies)

        # 집중 위험 감지
        high_correlation_pairs = []
        for i, s1 in enumerate(active_strategies):
            for j, s2 in enumerate(active_strategies[i+1:], i+1):
                if correlation_matrix[i][j] > correlation_threshold:
                    high_correlation_pairs.append((s1.agent_id, s2.agent_id))

        # 히트 점수 (0-100)
        heat_score = sum(1 for _ in high_correlation_pairs) * 10

        return HeatReport(
            score=min(heat_score, 100),
            high_correlation_pairs=high_correlation_pairs,
            recommendation=self.recommend_diversification(high_correlation_pairs)
        )
```

---

## 4. v2.0 통합 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Trinity v2.0 - Strategy Discovery Loop       │
└─────────────────────────────────────────────────────────────────┘

  ┌──────────────┐
  │  Historical  │
  │    Data      │
  │ (OHLCV etc)  │
  └──────┬───────┘
         │
         ▼
  ┌─────────────────────────────────┐
  │        Backtest Engine          │ ← 기존 ai_trading/core
  │  - IS/OOS Split                 │
  │  - Conservative Cost Model      │ ← 개선된 버전 적용
  │  - Trinity Score Calculation    │
  └──────────┬──────────────────────┘
             │
             ▼
  ┌─────────────────────────────────┐
  │         Risk Evaluation         │ ← 개선된 Risk Layer
  │  ┌─────────────────────────────┐│
  │  │ RAG Validator               ││ ← ai_expert 제안: Pattern Matching
  │  │ - Historical regime lookup  ││
  │  │ - Anti-pattern detection    ││
  │  └─────────────────────────────┘│
  │  ┌─────────────────────────────┐│
  │  │ Conservative Adjustments    ││ ← trader 제안: Cost Model
  │  │ - Slippage multiplier       ││
  │  │ - Fee buffer                ││
  │  └─────────────────────────────┘│
  │  ┌─────────────────────────────┐│
  │  │ Validation Gate             ││ ← 기존: OOS >= 0.7 * IS
  │  │ - Overfitting check         ││
  │  └─────────────────────────────┘│
  └──────────┬──────────────────────┘
             │
             ▼
  ┌─────────────────────────────────┐
  │           LLM Context           │ ← ai_trading/agents/llm_client
  │  - Performance feedback         │
  │  - Risk warnings                │
  │  - Pattern analysis             │
  └──────────┬──────────────────────┘
             │
             ▼
  ┌─────────────────────────────────┐
  │        LLM Strategy Mod           │
  │      (C-Mode Evolution)         │
  │  - Code generation                │
  │  - Self-correction                │
  │  - Security validation            │
  └──────────┬──────────────────────┘
             │
             ▼
  ┌─────────────────────────────────┐
  │      Supabase Storage           │ ← 통과한 전략만 저장
  │  - Strategy versions            │
  │  - Backtest results             │
  │  - Improvement logs             │
  └──────────┬──────────────────────┘
             │
             ▼
  ┌─────────────────────────────────┐
  │     v2 Dashboard                 │
  │  - Trinity Score comparison     │
  │  - Portfolio Heat visualization │
  │  - Strategy selection UI        │
  └─────────────────────────────────┘
```

---

## 5. v3.0으로 미뤄질 항목

다음은 실시간 실행 시 필요하나 v2.0에서 제외:

1. **Execution Engine (CCXT)**
   - 실제 거래소 API 연동
   - 주문 상태 관리 (PENDING, FILLED, CANCELLED)
   - Fill confirmation 및 장부 기록

2. **Real-time Risk Layer**
   - Position sizing on-the-fly
   - Circuit breaker (실시간 DD 모니터링)
   - Time decay (신호 수명 관리)

3. **Data Pipeline**
   - 실시간 WebSocket 데이터
   - Order Book depth 분석
   - On-chain metrics (지연성 있음)

---

## 6. Action Items

### 즉시 구현 가능 (v2.0)
- [ ] `BacktestRiskEvaluator` 클래스 구현
- [ ] `ConservativeCostModel` 튜닝 (multiplier 값 검증)
- [ ] `RAGValidator` 통합 (Vector DB 연결)
- [ ] Portfolio Heat 모니터링 (4 agents 병렬 실행 시)

### 분석 필요
- [ ] Anti-pattern 목록 정의 (어떤 패턴이 실패의 원인인가?)
- [ ] Kelly Criterion vs Half-Kelly 결정 기준
- [ ] RAG Vector DB 스키마 설계 (어떤 데이터를 저장할 것인가)

---

*Document Version: v2.0-risk-improved*
*Reviewed by: trader_expert + ai_expert collaboration*
*Scope: Backtesting-based Strategy Discovery (NOT live execution)*
