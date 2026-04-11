# Trinity v2.0 Architecture - Risk & Validation Layer (Trader Domain)

## 7. Risk & Validation Layer (Trader Domain)

### 7.1 Backtest Risk Evaluator

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

### 7.2 Conservative Cost Model

```python
class ConservativeCostModel:
    """
    항상 실제보다 보수적인 비용 모델 적용
    """

    # Anti-pattern 감지에서 자동 적용
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

        # 비용 조정 (과도한 거래 빈도 Anti-pattern)
        adjusted_return = gross_return - self.total_costs(trade_metrics)

        # MDD 보수적 조정 (과거 실패 패턴 기반)
        conservative_mdd = min(mdd * 1.2, -0.35)  # MDD 항상 20% 악화 가정

        return (adjusted_return * 0.45) + (sharpe * 20 * 0.35) + ((1 + conservative_mdd) * 100 * 0.20)

    def total_costs(self, trade_metrics: TradeMetrics) -> float:
        """보수적 비용 계산"""
        base_fee = trade_metrics.trade_count * 0.0005 * self.CONSERVATIVE_MULTIPLIERS['fee']
        slippage = trade_metrics.avg_slippage * self.CONSERVATIVE_MULTIPLIERS['slippage']
        spread_cost = trade_metrics.avg_spread * self.CONSERVATIVE_MULTIPLIERS['spread']

        return base_fee + slippage + spread_cost
```

### 7.3 IS/OOS Validation Gate

```python
class ValidationGate:
    """
    과적합 방지를 위한 In-Sample/Out-of-Sample 검증
    """

    def validate(self, is_metrics: BacktestMetrics, oos_metrics: BacktestMetrics) -> GateResult:
        """
        Rule: OOS score >= 0.7 * IS score
        """
        is_score = is_metrics.trinity_score
        oos_score = oos_metrics.trinity_score

        if is_score <= 0:
            passed = oos_score > 0
            ratio = float('inf') if oos_score > 0 else 0.0
        else:
            ratio = oos_score / is_score
            passed = ratio >= 0.7

        return GateResult(
            passed=passed,
            is_score=is_score,
            oos_score=oos_score,
            ratio=ratio,
            threshold=0.7,
            status="PASS" if passed else "OVERFIT_REJECT"
        )

    def split_data(self, data: pd.DataFrame, train_days: int = 30, val_days: int = 30) -> tuple:
        """
        최근 60일 데이터를 IS(30일) / OOS(30일)로 분할
        """
        total_window = train_days + val_days
        recent_data = data.tail(total_window)

        if len(recent_data) < total_window:
            # Fallback: 데이터 부족시 50/50 분할
            mid = len(data) // 2
            return data.iloc[:mid], data.iloc[mid:]

        split_point = train_days
        is_data = recent_data.iloc[:split_point]
        oos_data = recent_data.iloc[split_point:split_point + val_days]

        return is_data, oos_data
```

### 7.4 RAG-Based Validation (Pattern Matching)

```python
class RAGValidator:
    """
    RAG를 활용한 과적합 감지
    """

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

    def detect_antipatterns(self, backtest_result: BacktestMetrics) -> List[AntiPattern]:
        """
        알려진 실패 패턴 감지
        """
        known_failures = [
            Pattern.GRID_TRADE_CHOP,       # 횡보장에서 망하는 전략
            Pattern.MOMENTUM_LAG,            # 추세 전환 늦게 반응
            Pattern.HIGH_FREQUENCY_NOISE,    # 과도한 거래
            Pattern.VOLATILITY_CLUSTERS,       # 변동성 클러스터ing 무시
        ]

        detected = []
        for pattern in known_failures:
            if pattern.matches(signature=backtest_result.trade_signature):
                detected.append(pattern)

        return detected
```

### 7.5 Portfolio Heat Aggregator

```python
class PortfolioHeatAggregator:
    """
    여러 에이전트 전략의 동시 실행 리스크 평가
    백테스팅 관점에서의 correlation 분석
    """

    def calculate_portfolio_heat(
        self,
        active_strategies: List[Strategy],
        correlation_threshold: float = 0.7
    ) -> HeatReport:

        # 상관관계 배열 (과거 수익률 기준)
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

### 7.6 Risk → Validation Contract

```json
{
  "version": "2.0.0",
  "validation_type": "IS_OOS_RAG_COMBINED",
  "is_validation": {
    "passed": true,
    "trinity_score": 145,
    "sharpe": 2.1,
    "mdd": -5.2,
    "trade_count": 85
  },
  "oos_validation": {
    "passed": true,
    "trinity_score": 132,
    "sharpe": 1.9,
    "mdd": -6.1,
    "trade_count": 42
  },
  "ratio_check": {
    "ratio": 0.91,
    "threshold": 0.7,
    "passed": true
  },
  "rag_validation": {
    "pattern_matches": 3,
    "historical_avg_score": 138,
    "current_above_threshold": true
  },
  "cost_adjustment": {
    "gross_return": 15.2,
    "conservative_return": 12.8,
    "fee_impact": 1.2,
    "slippage_impact": 1.1
  },
  "antipatterns_detected": [],
  "final_decision": "ACCEPT",
  "feedback_for_llm": "Strong IS/OOS consistency. Low correlation with active strategies."
}
```

---

## 8. Trinity Score Calculation (Enhanced)

### 8.1 Original Formula

```
Trinity Score = Return × 0.40 + Sharpe × 25 × 0.35 + (1 + MDD) × 100 × 0.25

Weights:
- Return: 40% (profitability)
- Sharpe: 35% (risk-adjusted return)
- MDD: 25% (downside protection)
```

### 8.2 Conservative Cost-Adjusted Formula

```
Adjusted Trinity Score = Conservative_Return × 0.45 + Sharpe × 20 × 0.35 + (1 + Conservative_MDD) × 100 × 0.20

Where:
- Conservative_Return = Gross_Return - Total_Costs
- Conservative_MDD = min(MDD × 1.2, -0.35)
- Total_Costs = (Fee × 1.5) + (Slippage × 2.0) + (Spread × 1.3)

Rationale:
- Higher weight on cost-adjusted return (45% vs 40%)
- Conservative Sharpe multiplier (20 vs 25)
- MDD floor at -35%
```

---

## 9. v2.0 vs v3.0 Scope Clarification

### v2.0 (Current) - 백테스팅 중심 전략 발견

| Feature | Status | Notes |
|---------|--------|-------|
| Historical Data Pipeline | ✅ P0 | CSV/API 기반 |
| Backtest Engine | ✅ P0 | IS/OOS Split |
| Risk Validation | ✅ P0 | Conservative Cost |
| RAG Validation | ✅ P1 | Pattern Matching |
| Portfolio Heat | ✅ P1 | Correlation Analysis |
| Real-time Data Streams | ❌ v3.0 | WebSocket feeds |
| Live Execution | ❌ v3.0 | CCXT integration |
| Smart Order Routing | ❌ v3.0 | Order management |
| Circuit Breakers | ❌ v3.0 | Real-time DD monitoring |

### Key Difference

- **v2.0**: 전략 코드를 생성하고 백테스팅으로 검증 → 높은 Trinity Score 전략 선별
- **v3.0**: 검증된 전략을 실시간 실행 → 실제 매매 및 포트폴리오 관리

---

*Document: Trinity v2.0 Risk & Validation Layer*
*Prepared by: Trader Expert*
*Status: Complete*
