# Trinity v2.0 AI Architecture Proposal

**Analyst:** ai_expert  
**Date:** 2026-04-11  
**Status:** Integration Complete (含 Analyst反馈)

---

## 1. Executive Summary

백테스팅 기반 전략 최적화에 초점을 맞춘 AI Architecture 개선안. Analyst 전문가의 데이터 품질 gates와 regime detection 파이프라인을 통합.

---

## 2. Integrated AI-RAG Pipeline

### 2.1 Pipeline Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA PIPELINE (Analyst)                   │
│  Real-time Feed → Feature Engineer → Quality Gates          │
│                                    ↓                        │
│                           Online Regime Detection           │
└─────────────────────────────────────────────────────────────┘                               ↓
┌─────────────────────────────────────────────────────────────┐
│                    AI BRAIN (AI Expert)                    │
│  Structured JSON → Tabular Context                          │
│       ↓                                                     │
│  RAG: Retrieve similar regime strategies (verified, score>130)
│       ↓                                                     │
│  LLM: Generate improved strategy code                       │
└─────────────────────────────────────────────────────────────┘                               ↓
┌─────────────────────────────────────────────────────────────┐
│                    BACKTEST ENGINE                          │
│  Execute → Metrics (Sharpe, Win Rate, MDD)                  │
│       ↓                                                     │
│  Improvement? → Commit to RAG KB : Reject                   │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Feature Quality Gates (Analyst 제안 통합)

```python
def validate_features_for_llm(features: dict) -> bool:
    """LLM context로 사용하기 전 데이터 품질 검증"""
    checks = [
        # NaN/Inf 체크
        all(np.isfinite(v) for v in features.values()),
        # Z-score 범위 (-5 ~ +5)
        all(abs(features.get(f"{k}_zscore", 0)) < 5 for k in features),
        # 데이터 freshness (5초 이내)
        (datetime.now() - features.timestamp).seconds < 5,
        # 최소 필수 필드 존재
        all(k in features for k in ["price", "volume", "volatility"])
    ]
    return all(checks)
```

### 2.3 Online Regime Detection (Analyst 제안 통합)

```python
class OnlineRegimeClassifier:
    """실시간 시장 국면 분류기"""
    def detect(self, features: FeatureVector) -> Regime:
        # Volatility Regime
        vol_percentile = features.volatility.percentile(30)
        vol_regime = "High" if vol_percentile > 80 else \
                     "Low" if vol_percentile < 20 else "Normal"
        
        # Trend Regime
        adx = features.trend.adx(14)
        trend_regime = "Trending" if adx > 40 else \
                       "Ranging" if adx < 20 else "Transition"
        
        return Regime(f"{trend_regime}_{vol_regime}")
```

---

## 3. Context Assembly Architecture (v2.1)

### 3.1 Structured → Tabular 변환

```python
class ContextAssembler:
    VERSION = "2.1.0"
    
    def assemble(self, market_data: dict) -> str:
        # 1. Quality Gates (Analyst 제안)
        if not validate_features_for_llm(market_data):
            raise DataQualityError("Features failed quality gates")
        
        # 2. Regime Detection (Analyst 제안)
        regime = OnlineRegimeClassifier().detect(market_data)
        
        # 3. Structured → Tabular
        table = self.to_markdown_table(market_data)
        
        # 4. RAG Retrieval with filters
        similar = rag.query(
            vector=embed(table),
            filters={
                "verified": True,
                "trinity_score": {"$gt": 130},
                "regime": regime.value  # Regime 기반 필터
            },
            top_k=5
        )
        
        # 5. Versioned Prompt Assembly with XML tagging
        return self._assemble_prompt(table, similar, regime)
    
    def _assemble_prompt(self, table: str, patterns: list, regime: Regime) -> str:
        return f"""<context_version>{self.VERSION}</context_version>

<regime>
Current: {regime.value}
Confidence: {regime.confidence}
</regime>

<market_context>
{table}
</market_context>

<retrieved_patterns count="{len(patterns)}">
{self.format_patterns(patterns)}
</retrieved_patterns>

<instruction>
Generate strategy optimized for current regime.
Patterns above show successful strategies in similar conditions.
</instruction>
"""
```

### 3.2 Context Schema (Versioned)

```python
class ContextSchema:
    """Context format 버전 관리"""
    VERSION = "2.1.0"
    
    SCHEMA = {
        "regime": {"required": True, "type": "object"},
        "market_snapshot": {"required": True, "type": "table"},
        "on_chain": {"required": True, "type": "table"},
        "risk_dashboard": {"required": True, "type": "table"},
        "rag_patterns": {
            "required": True,
            "type": "list",
            "max_items": 5,
            "filter": {"verified": True, "trinity_score": {"$gt": 130}}
        }
    }
```

---

## 4. RAG Knowledge Base Structure

### 4.1 Document Types

| Type | Content | Embedding | Filter Fields |
|------|---------|-----------|---------------|
| `strategy_patterns` | 성공 전략 코드 AST | text-embedding-3-large | verified, trinity_score, regime |
| `regime_fingerprints` | 시장 국면 시그니처 | text-embedding-3-large | date_range, volatility_percentile |
| `loss_explanations` | 실패 원인 분석 | text-embedding-3-large | strategy_id, failure_mode |
| `evolution_lineage` | 전략 변화 궤적 | text-embedding-3-large | agent_id, generation |

### 4.2 Query Strategy

```python
class RAGQueryBuilder:
    def build(self, regime: Regime, features: dict) -> dict:
        """
        Multi-stage retrieval:
        1. Regime-based filter (exact match)
        2. Performance filter (trinity_score > 130)
        3. Similarity search (embedding)
        4. Rerank by recency
        """
        return {
            "filter": {
                "regime": regime.value,
                "verified": True,
                "trinity_score": {"$gt": 130}
            },
            "vector": embed(features),
            "top_k": 10,
            "rerank": {"field": "timestamp", "order": "desc"}
        }
```

---

## 5. Hallucination Reduction Mechanisms

### 5.1 Layered Validation

| Layer | Mechanism | Purpose |
|-------|-----------|---------|
| 1 | Structured → Tabular | Format hallucination 방지 |
| 2 | Quality Gates | Data quality hallucination 방지 |
| 3 | Regime Detection | Context hallucination 방지 |
| 4 | RAG Filtering | Pattern hallucination 방지 |
| 5 | XML Tagging | Parsing hallucination 방지 |
| 6 | Backtest Validation | Strategy hallucination 방지 |

### 5.2 Self-Correction Loop (v2)

```python
class HallucinationGuard:
    def validate(self, generated_code: str, context: dict) -> ValidationResult:
        checks = [
            SyntaxChecker().check(generated_code),  # 기존
            SemanticValidator().check(generated_code, context["regime"]),  # 신규
            PatternMatcher().check(generated_code, context["rag_patterns"]),  # 신규
            BacktestValidator().simulate(generated_code, n_bars=100)  # 신규
        ]
        return all(checks)
```

---

## 6. Implementation Priority (Revised)

| Priority | Feature | Owner | Dependency |
|----------|---------|-------|------------|
| P0 | Feature Quality Gates | Analyst | - |
| P0 | Online Regime Detection | Analyst | Quality Gates |
| P1 | Context Assembly v2.1 | AI | Regime Detection |
| P1 | RAG KB with Filters | AI | Context Assembly |
| P2 | Hallucination Guard v2 | AI | RAG KB |
| P2 | Context Versioning | AI | - |
| P3 | Self-Correction Loop | AI | Hallucination Guard |

---

## 7. Integration Checklist

- [x] Structured signal format (JSON → Tabular)
- [x] RAG filters (verified, trinity_score>130)
- [x] Quality Gates specification
- [x] Online Regime Detection spec
- [x] Context Versioning schema
- [ ] Trader Expert Risk/Validation input pending
- [ ] Backtest validation integration (static → streaming)
- [ ] Performance benchmarking

---

*Next: Awaiting trader_expert Risk/Validation perspective for final integration*
