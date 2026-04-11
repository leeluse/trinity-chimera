# Trinity v2.0 Data Architecture Blueprint

**Analyst:** analyst_expert (Cryptocurrency Market Analysis Specialist)  
**Date:** 2026-04-11  
**Purpose:** Final data source map and RAG ingestion pipeline for Trinity v2.0  

---

## 1. Data Source Map

### 1.1 Real-Time Market Data Sources

| Signal | API Source | Endpoint | Frequency | Processing Method | Latency Target |
|--------|-----------|----------|-----------|-------------------|----------------|
| **price_ohlcv** | Binance WebSocket | `wss://stream.binance.com:9443/ws/btcusdt@kline_1m` | Tick-by-tick | VWAP normalization | <50ms |
| **orderbook_l2** | Binance Diff Depth | `wss://stream.binance.com:9443/ws/btcusdt@depth@100ms` | 100ms snapshot | Liquidity-weighted Imbalance calc | <100ms |
| **trades_flow** | Binance Aggregate | `wss://stream.binance.com:9443/ws/btcusdt@aggTrade` | Real-time | Buy vs Sell volume ratio | <50ms |
| **liquidations** | Binance Futures | `wss://fstream.binance.com/ws/btcusdt@forceOrder` | Real-time | Cumulative sum (1m window) | <50ms |
| **funding_rate** | Binance Funding | REST: `/fapi/v1/fundingRate` | Every 8 hours | Z-score vs 30-day hist | <200ms |
| **open_interest** | Binance OI | REST: `/fapi/v1/openInterest` | 1 minute | Delta vs 1h ago | <200ms |

### 1.2 On-Chain Data Sources

| Signal | Provider | Endpoint | Frequency | Processing Method |
|--------|----------|----------|-----------|-------------------|
| **exchange_inflow** | Glassnode | `/v1/metrics/exchanges/inflow_usd` | 1 hour | Net flow (in - out) |
| **exchange_outflow** | Glassnode | `/v1/metrics/exchanges/outflow_usd` | 1 hour | Net flow (in - out) |
| **whale_movement** | Whale Alert | Webhook API | Real-time | Threshold: >$10M USD |
| **whale_ratio** | Glassnode | `/v1/metrics/supply/holding_distribution` | 1 hour | % held by 1k+ BTC wallets |
| **addr_active** | Glassnode | `/v1/metrics/addresses/active_count` | 1 hour | 7-day MA |
| **nvt_ratio** | Glassnode | `/v1/metrics/indicators/nvt` | 1 day | Z-score vs 90-day |
| **mvrv_ratio** | Glassnode | `/v1/metrics/indicators/sopr` | 1 day | Regime classification |
| **nupl** | Glassnode | `/v1/metrics/indicators/nupl` | 1 day | Sentiment zone |
| **sopr** | Glassnode | `/v1/metrics/indicators/sopr` | 1 hour | Short-term trend |
| **hash_rate** | Glassnode | `/v1/metrics/mining/hash_rate_mean` | 1 day | 7-day delta |

### 1.3 Alternative/Derived Sources

| Signal | Provider | Purpose | Frequency |
|--------|----------|---------|-----------|
| **fear_greed** | Alternative.me | Market sentiment | Daily |
| **options_skew** | Deribit | Risk sentiment | 5 minutes |
| **vol_term_structure** | Deribit | Volatility regime | 15 minutes |
| **gas_oracle** | ETH Gas Station | Network congestion | Real-time |
| **defi_tvl** | DeFi Llama | DeFi health | 1 hour |

---

## 2. Signal Structure for AI Reasoning

### 2.1 Standardized Signal Format

All data flows through the pipeline as structured JSON to minimize hallucination:

```json
{
  "signal_id": "uuid-v4",
  "timestamp": "2026-04-11T12:00:00.000Z",
  "symbol": "BTCUSDT",
  "timeframe": "1m",
  "signal_type": "market_microstructure",
  "payload": {
    "price": {
      "open": 69420.50,
      "high": 69500.00,
      "low": 69380.00,
      "close": 69450.00,
      "vwap": 69435.20,
      "change_pct": 0.04
    },
    "volume": {
      "total": 1234.56,
      "buy": 823.45,
      "sell": 411.11,
      "buy_sell_ratio": 2.0
    },
    "orderbook": {
      "bid_depth": 234.5,
      "ask_depth": 189.3,
      "imbalance": 0.24,
      "spread_pct": 0.08,
      "best_bid": 69449.50,
      "best_ask": 69450.50
    },
    "liquidity": {
      "bid_slope": 12.3,
      "ask_slope": 8.7,
      "toxicity_flow": -0.15
    }
  },
  "metadata": {
    "data_quality": "high",
    "latency_ms": 45,
    "source_reliability": 0.998
  }
}
```

### 2.2 Feature Engineering Pipeline

```python
class FeatureEngine:
    """Transform raw data into LLM-friendly features"""

    def calculate_features(self, window: DataWindow) -> FeatureVector:
        return {
            # Price Action
            "trend_strength": self._adx(window.ohlcv, period=14),
            "volatility_regime": self._atr_percentile(window.ohlcv, lookback=30),
            "momentum": self._rsi(window.ohlcv.close, period=14) / 100,

            # Market Microstructure
            "orderflow_imbalance": self._ofv(window.trades),
            "liquidity_score": self._liquidity_score(window.orderbook),
            "spread_regime": self._normalize_spread(window.orderbook.spread),

            # On-Chain Context
            "exchange_pressure": self._netflow_ma(window.exchange_flow, period=24),
            "whale_accumulation": self._whale_ratio_delta(window.whale_data),
            "network_health": self._network_score(window.chain_metrics),

            # Sentiment/Crowd
            "funding_sentiment": self._funding_zscore(window.funding),
            "fear_greed_zone": self._fg_index_category(window.sentiment),

            # Risk Indicators
            "liquidation_cluster": self._liq_cluster_density(window.liquidations),
            "vol_skew": self._options_skew_regime(window.options)
        }
```

### 2.3 LLM Context Assembly

```python
class LLMContextBuilder:
    """Build structured context for C-mode prompts"""

    def build_context(self, features: FeatureVector, kb_insights: List[RetrievedDoc]) -> str:
        return f"""
### Market Snapshot (Last Update: {features.timestamp})
| Metric | Value | Regime | Z-Score |
|--------|-------|--------|---------|
| Price | ${features.price.close:,.2f} | {features.trend_regime} | {features.price_zscore:.2f} |
| Volatility | {features.volatility.annualized:.1%} | {features.vol_regime} | {features.vol_zscore:.2f} |
| Liquidity | {features.liquidity_score:.2f}/10 | {features.liq_regime} | {features.liq_zscore:.2f} |
| Order Flow | {features.flow_imbalance:.3f} | {features.flow_regime} | {features.flow_zscore:.2f} |

### On-Chain Signals
- Exchange Netflow: {features.exchange_pressure:+.2f} BTC (24h)
- Whale Ratio Δ: {features.whale_delta:+.2%} (vs 7d avg)
- MVRV: {features.mvrv:.2f} → {features.mvrv_regime}
- NUPL: {features.nupl:.3f} → {features.nupl_zone}

### Risk Dashboard
- Liquidation Clusters: {features.liq_clusters}
- Funding Premium: {features.funding_annualized:.2%}
- OI Change: {features.oi_change:+.2%} (24h)
- Max Pain: ${features.options_max_pain:,.0f}

### Relevant Historical Patterns (RAG)
{self._format_kb_insights(kb_insights)}
"""
```

---

## 3. RAG Knowledge Base Design

### 3.1 Document Types

| Collection | Content Source | Update Frequency | Embedding Model |
|------------|---------------|------------------|-----------------|
| **strategy_patterns** | Backtest winners + losers | After each evolution | text-embedding-3-large |
| **regime_fingerprints** | Market regime clusters | Daily | text-embedding-3-large |
| **loss_explanations** | Failed trade analysis | Real-time | text-embedding-3-large |
| **macro_events** | News + economic calendar | Hourly | text-embedding-3-large |

### 3.2 Document Schema

```json
{
  "doc_id": "strategy_v1234",
  "collection": "strategy_patterns",
  "content": {
    "summary": "Mean reversion strategy with ATR filtering performed well in choppy markets",
    "code_snippet": "def generate_signal(data): ...",
    "performance": {
      "trinity_score": 145,
      "sharpe": 2.1,
      "mdd": -5.2,
      "win_rate": 0.68
    },
    "market_context": {
      "regime": "ranging",
      "vol_percentile": 45,
      "correlation_btc": 0.82
    },
    "why_worked": "ATR filter avoided low-volatility traps",
    "why_failed": "Missed breakout moves due to filter lag"
  },
  "embedding": [0.023, -0.156, ...],
  "metadata": {
    "timestamp": "2026-04-10T00:00:00Z",
    "agent_id": "mean_reverter",
    "version": 12,
    "verified": true
  }
}
```

### 3.3 Ingestion Pipeline

```python
class RAGIngestionPipeline:
    """Ingest backtest results into vector DB"""

    async def ingest_backtest(self, result: BacktestResult):
        # 1. Generate strategy summary
        summary = await self.llm.summarize(
            code=result.strategy_code,
            metrics=result.metrics,
            market_regime=result.regime
        )

        # 2. Create regime fingerprint
        fingerprint = {
            "vol_regime": result.vol_percentile_bucket,
            "trend_strength": result.adx_category,
            "liquidity_regime": result.liquidity_score_bucket,
            "on_chain_zone": result.chain_sentiment
        }

        # 3. Build document
        doc = StrategyDocument(
            summary=summary,
            code_snippet=self._extract_key_logic(result.strategy_code),
            performance=result.metrics,
            market_context=fingerprint,
            why_worked=result.success_factors,
            why_failed=result.failure_factors
        )

        # 4. Generate embedding
        embedding = await self.embedding_model.create(
            self._format_for_embedding(doc)
        )

        # 5. Store in vector DB
        await self.vector_db.upsert(
            collection="strategy_patterns",
            documents=[{"embedding": embedding, "metadata": doc}]
        )

    async def query_similar_strategies(self, current_context: FeatureVector, k: int = 5):
        """Retrieve relevant historical patterns"""
        query_embedding = await self.embedding_model.create(
            self._context_to_text(current_context)
        )

        return await self.vector_db.search(
            collection="strategy_patterns",
            vector=query_embedding,
            filter={"verified": True, "trinity_score": {"$gt": 130}},
            top_k=k
        )
```

### 3.4 Query Patterns

| Query Type | Use Case | Filters |
|------------|----------|---------|
| Similar Regime | "What worked in similar conditions?" | regime_fingerprint match |
| High Performers | "Best strategies by Trinity Score" | trinity_score > 140 |
| Loss Analysis | "Why did strategies fail?" | mdd > 15%, verified=true |
| Recent Patterns | "Latest successful adaptations" | last 7 days |

---

## 4. Data Quality & Validation

### 4.1 Quality Gates

```python
class DataQualityGate:
    """Enforce data quality before processing"""

    def validate(self, tick: MarketTick) -> ValidationResult:
        checks = {
            "freshness": self._check_freshness(tick.timestamp, max_age_sec=5),
            "price_bounds": self._check_price_bounds(tick.price, lookback=100),
            "volume_min": tick.volume > self.min_volume_threshold,
            "spread_sanity": 0 < tick.spread_pct < 5.0,  # <5%
            "exchange_healthy": self.exchange_health[tick.exchange] == "up",
            "no_duplicates": tick.id not in self.recent_ids
        }

        return ValidationResult(
            passed=all(checks.values()),
            failures=[k for k, v in checks.items() if not v],
            quality_score=sum(checks.values()) / len(checks)
        )
```

### 4.2 Monitoring Metrics

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Data Latency (p99) | <100ms | >200ms |
| Missing Data Rate | <0.1% | >0.5% |
| Quality Gate Pass Rate | >99% | <95% |
| On-Time Arrival | >99.9% | <99% |
| RAG Query Latency | <50ms | >100ms |

---

## 5. Integration with Risk & Execution

### 5.1 Signal Flow Architecture

```
┌─────────────────────┐
│   Raw Data Feeds    │
│  (Binance, Glassnode) │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   Quality Gates     │
│  Freshness, bounds   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   Feature Engine     │
│  + Real-time calc    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   RAG Enrichment     │
│  + Historical matches│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   LLM Context        │
│  Build structured    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   AI Brain           │
│  Generate signal     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   Risk Guardrail    │
│  Validate signal     │
│  Size position       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   Execution Engine   │
│  Route to exchange   │
└─────────────────────┘
```

### 5.2 Risk Guardrail Data Requirements

| Risk Check | Data Source | Calculation | Threshold |
|------------|-------------|-------------|-----------|
| Position limit | Portfolio state | Current exposure | < 10% NAV |
| Vol scaling | Realized vol | ATR(14) / Price | Dynamic |
| Correlation check | Position correlation | Rolling correlation matrix | < 0.7 |
| Liquidity check | Orderbook depth | Can exit within slippage? | < 50bps |
| Drawdown guard | P&L tracking | Peak-to-trough | < 15% |

---

## 6. Validation Against Requirements

### 6.1 Coverage Matrix

| Requirement | Source | Status |
|-------------|--------|--------|
| Real-time market data | Binance WebSocket | ✅ Covered |
| Orderbook depth | Binance Depth Stream | ✅ Covered |
| On-chain metrics | Glassnode | ✅ Covered |
| Whale tracking | Whale Alert + Glassnode | ✅ Covered |
| Exchange flows | Glassnode Exchange API | ✅ Covered |
| Sentiment data | Alternative.me + Funding | ✅ Covered |
| RAG Integration | Custom ingestion pipeline | ✅ Covered |
| Quality gates | Multi-layer validation | ✅ Covered |

---

## 7. Implementation Phases

### Phase 1 (Sprint 1-2): Core Market Data
- Binance WebSocket integration
- OHLCV + Orderbook streaming
- Basic quality gates

### Phase 2 (Sprint 3-4): On-Chain Integration
- Glassnode API setup
- Whale alert webhooks
- Exchange flow tracking

### Phase 3 (Sprint 5-6): RAG & Feature Engineering
- Vector DB setup (Pinecone/Weaviate)
- Feature calculation engine
- Context assembly pipeline

### Phase 4 (Sprint 7-8): Production Hardening
- Multi-exchange failover
- Latency optimization
- Comprehensive monitoring

---

*Blueprint provided by analyst_expert for integration into trinity-v2-architecture.md*
