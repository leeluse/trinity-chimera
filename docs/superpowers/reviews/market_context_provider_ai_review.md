# AI Expert Review: MarketContextProvider

**Date:** 2026-04-11  
**Reviewer:** ai_expert  
**Status:** Code Review Complete, Fixes Applied

---

## Executive Summary

`MarketContextProvider`는 RAG 기반 전략 진화를 위한 핵심 컴포넌트입니다. 기본 구조는 적절하나 AI 추론 관점에서 몇 가지 개선이 필요합니다.

---

## Code Fixes Applied

### Bug Fix: Bitwise Shift Operators

**Issue:** 라인 39, 57에서 `<<` (bitwise shift)가 `<` (less than)의 오타로 사용됨

```python
# Before (Bug)
vol_level = "High" if vol_percentile > 70 else "Low" if vol_percentile << 30 else "Medium"
if len(returns) << 2: return 0.0

# After (Fixed)
vol_level = "High" if vol_percentile > 70 else "Low" if vol_percentile < 30 else "Medium"
if len(returns) < 2: return 0.0
```

**Impact:** Without this fix, `vol_percentile << 30` would bit-shift the value (e.g., 50 << 30 = 53687091200), causing incorrect "Low" volatility classification.

---

## AI Domain Assessment

### Positive Findings

1. **Structured Regime Classification**: "Volatile Bull", "Low-Vol Ranging" 등 LLM이 이해하기 쉬운 카테고리
2. **Quantitative Metrics**: volatility_percentile, trend_strength 제공
3. **Boolean Flags**: is_trending은 rule-based 접근에 유용

### Critical Gaps for AI/RAG

#### 1. Missing: Context Confidence Score

```python
@dataclass
class MarketContext:
    regime: str
    volatility_percentile: float
    trend_strength: float
    is_trending: bool
    volatility_level: str
    confidence: float  # ADD: Model confidence in regime classification
    data_quality: str  # ADD: "full", "partial", "stale"
```

**Why**: LLM needs to know how much to trust the regime signal. Low confidence → conservative strategy suggestion.

#### 2. Missing: Historical Pattern References

```python
@dataclass
class MarketContext:
    # ... existing fields ...
    similar_regimes: List[str]  # ADD: Past regime IDs for RAG retrieval
    avg_strategy_performance: Dict[str, float]  # ADD: Historical performance by regime
```

**Why**: RAG retrieval requires regime IDs, not just current state.

#### 3. Missing: Multi-Timeframe Context

```python
class MarketContextProvider:
    async def get_context(self, symbol: str, timeframe: str) -> MarketContext:
        # Current: single timeframe
        # Needed: Multi-timeframe consensus
        contexts = await asyncio.gather([
            self._get_single_context(symbol, tf) 
            for tf in ["1h", "4h", "1d"]
        ])
        return self._aggregate_contexts(contexts)  # ADD: Consensus regime
```

**Why**: Single timeframe can give false signals. Multi-timeframe alignment increases confidence.

---

## Recommendations

### P1: Add Confidence Scoring

```python
def _calculate_confidence(self, vol_perc: float, trend_strength: float, data_freshness: int) -> float:
    """
    Confidence based on:
    - Data age (0-1, older = lower)
    - Metric stability (volatility of volatility)
    - Sample size for calculations
    """
    freshness_score = max(0, 1 - (data_freshness / 300))  # 5 min = 300s
    stability_score = self._calculate_metric_stability()
    sample_score = min(1.0, len(self.data) / 100)
    
    return (freshness_score + stability_score + sample_score) / 3
```

### P2: Add RAG Integration Hook

```python
def to_rag_query(self) -> Dict:
    """Convert context to RAG query parameters"""
    return {
        "regime": self.regime,
        "vol_percentile_range": [self.volatility_percentile - 10, self.volatility_percentile + 10],
        "trend_strength_range": [self.trend_strength * 0.8, self.trend_strength * 1.2],
        "filter": {"verified": True, "trinity_score": {"$gt": 130}}
    }
```

### P3: Add Context Validation

```python
def validate_for_llm(self) -> bool:
    """Ensure context meets minimum requirements for LLM consumption"""
    return all([
        self.volatility_percentile > 0,
        self.trend_strength >= 0,
        self.confidence > 0.5,  # Threshold for reliable signal
        self.data_quality != "stale"
    ])
```

---

## Integration with v2.0 Architecture

Current `MarketContext` maps to v2.0 architecture as follows:

| v2.0 Component | MarketContext Field | Usage |
|----------------|---------------------|-------|
| Quality Gates | data_quality | P0 validation |
| Regime Detection | regime, is_trending | Core classification |
| Context Assembly | volatility_percentile, trend_strength | LLM prompt input |
| RAG Retrieval | regime | Filter parameter |
| Confidence Thresholding | confidence | Risk gating |

---

## Conclusion

**Approval Status**: Conditional Approval

`MarketContextProvider`는 기본 기능을 제공하나 **confidence scoring**과 **RAG integration hooks** 추가 없이는 production RAG 파이프라인에 통합하기 어렵습니다.

**Required for Integration**:
1. ✅ Bitwise shift bug fix (completed)
2. 🔄 Confidence score calculation (P1)
3. 🔄 to_rag_query() method (P1)
4. 🔄 Multi-timeframe support (P2)

**Recommended**: 위 P1/P2 항목 구현 후 `EvolutionOrchestrator`에 통합하세요.
