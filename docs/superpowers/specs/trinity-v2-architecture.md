# Trinity v2.0 Architecture Specification

**Document:** Trinity AI Trading System v2.0 Architecture  
**Status:** Draft v0.9 (Analyst Feedback Integrated, Trader Input Pending)  
**Last Updated:** 2026-04-11  

---

## Executive Summary

Trinity v2.0은 **백테스팅 기반 전략 최적화**를 핵심 목표로 아키텍처를 재설계합니다. Data Pipeline → AI Brain → Backtest Engine의 통합 파이프라인을 통해 더 높은 Sharpe, Win Rate, 더 낮은 MDD를 달성하는 전략을 자율적으로 발전시킵니다.

---

## 1. System Architecture Overview

### 1.1 High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATA LAYER (Analyst)                          │
│  ┌──────────────┐   ┌────────────────┐   ┌─────────────────────┐       │
│  │ Real-time    │ → │ Feature Eng    │ → │ Quality Gates (P0)  │       │
│  │ Data Feed    │   │ Multi-timeframe│   │ NaN/Z-score/Fresh   │       │
│  └──────────────┘   └────────────────┘   └─────────────────────┘       │
│                                                       │                  │
│                                                       ↓                  │
│                            ┌─────────────────────────────────┐         │
│                            │ Online Regime Detection (P1)    │         │
│                            │ Trend + Volatility Classifier   │         │
│                            └─────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────────────────┘
                                         ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                         AI BRAIN (AI Expert)                            │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Context Assembler v2.1                                          │   │
│  │  1. Structured JSON → Markdown Table                             │   │
│  │  2. RAG Query: verified=true, trinity_score>130, regime=match  │   │
│  │  3. LLM Generate: Strategy Code with few-shot patterns         │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                    │                                    │
│                                    ↓                                    │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Hallucination Guard v2                                          │   │
│  │  - Semantic Validation: Pattern matching                          │   │
│  │  - Backtest Sandbox: 100-bar simulation                         │   │
│  │  - Anti-pattern Check: Known failures                           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                         ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                      BACKTEST ENGINE                                    │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Strategy Validation                                               │   │
│  │  - AST Security Check (forbidden imports)                         │   │
│  │  - Backtest Execution (multi-regime)                              │   │
│  │  - Metrics: Sharpe, Win Rate, MDD, Calmar                          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                    │                                    │
│                                    ↓                                    │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Decision: Trinity Score Improvement?                              │   │
│  │  YES → Commit to RAG Knowledge Base                               │   │
│  │  NO  → Log failure, update anti-patterns                          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Specifications

### 2.1 Data Pipeline (Analyst Domain)

#### 2.1.1 Quality Gates Specification

```python
def validate_features_for_llm(features: dict) -> ValidationResult:
    """
    P0: 데이터 품질 검증 without which LLM input is unreliable
    
    Checks:
    1. NaN/Inf detection: all(np.isfinite(v) for v in features.values())
    2. Z-score bounds: -5 < zscore < +5 (outlier detection)
    3. Freshness: data timestamp < 5 seconds old
    4. Completeness: required fields ["price", "volume", "volatility"]
    
    Returns: ValidationResult(valid: bool, failed_checks: list)
    """
    checks = {
        "finite": all(np.isfinite(v) for v in features.values()),
        "zscore": all(abs(features.get(f"{k}_zscore", 0)) < 5 for k in features),
        "freshness": (datetime.now() - features.timestamp).seconds < 5,
        "completeness": all(k in features for k in REQUIRED_FIELDS)
    }
    return ValidationResult(all(checks.values()), checks)
```

#### 2.1.2 Regime Detection

```python
class OnlineRegimeClassifier:
    """
    P1: 실시간 시장 국면 분류
    
    Combines:
    - Volatility Regime: High (>80p), Normal, Low (<20p)
    - Trend Regime: Trending (ADX>40), Ranging (ADX<20), Transition
    
    Output: Regime("Trending_High", "Ranging_Low", etc.)
    """
    
    def detect(self, features: FeatureVector) -> Regime:
        vol_percentile = features.volatility.percentile(30)
        vol_regime = self._classify_volatility(vol_percentile)
        
        adx = features.trend.adx(14)
        trend_regime = self._classify_trend(adx)
        
        return Regime(f"{trend_regime}_{vol_regime}", confidence=...)
```

### 2.2 AI Brain (AI Expert Domain)

#### 2.2.1 Context Assembly v2.1

```python
class ContextAssembler:
    """
    Versioned context assembly with Analyst-specified quality gates
    """
    VERSION = "2.1.0"
    
    async def assemble(self, market_data: dict) -> str:
        # P0: Quality gates (Analyst requirement)
        validation = validate_features_for_llm(market_data)
        if not validation.valid:
            raise DataQualityError(f"Failed: {validation.failed_checks}")
        
        # P1: Regime detection (Analyst specification)
        regime = await self.regime_classifier.detect(market_data)
        
        # Structured → Tabular (reduces hallucination)
        table = self._to_markdown_table(market_data)
        
        # RAG retrieval with verified + score filter
        patterns = await self.rag.query(
            vector=embed(table),
            filters={
                "verified": True,
                "trinity_score": {"$gt": 130},
                "regime": regime.value  # Must match current regime
            },
            top_k=5
        )
        
        return self._assemble_xml_prompt(regime, table, patterns)
    
    def _assemble_xml_prompt(self, regime, table, patterns) -> str:
        return f"""<context version="{self.VERSION}">
<regime type="{regime.value}" confidence="{regime.confidence}">
{regime.summary}
</regime>

<market_data>
{table}
</market_data>

<reference_patterns count="{len(patterns)}">
{self._format_patterns(patterns)}
</reference_patterns>
</context>

<instruction>
Generate strategy code optimized for current regime.
Reference patterns above show successful approaches in similar conditions.
</instruction>
"""
```

#### 2.2.2 RAG Knowledge Base Schema

```
Collection: strategy_patterns
- id: string (UUID)
- code: string (strategy code AST)
- embedding: vector (1536-dim)
- metadata:
  - trinity_score: float
  - sharpe: float
  - win_rate: float
  - mdd: float
  - regime: string (e.g., "Trending_High")
  - verified: boolean
  - created_at: timestamp
  - evolved_from: string (parent strategy id)

Collection: regime_fingerprints
- id: string
- features: dict (normalized market features)
- embedding: vector
- metadata:
  - regime_label: string
  - date_range: [start, end]
  - dominant_strategy: string
  - avg_trinity_score: float

Collection: anti_patterns
- id: string
- pattern_type: string ("overfit", "regime_mismatch", "logic_error")
- description: string
- example_strategy: string
- failure_metrics: dict
```

#### 2.2.3 Hallucination Guard v2

```python
class HallucinationGuard:
    """
    Multi-layer validation before strategy code acceptance
    """
    
    async def validate(self, code: str, context: AssemblyContext) -> GuardResult:
        checks = [
            # Layer 1: Syntax
            SyntaxChecker().validate(code),
            
            # Layer 2: Security (existing)
            SecurityChecker().validate(code),
            
            # Layer 3: Semantic (new)
            SemanticValidator().validate(code, context.regime),
            
            # Layer 4: Pattern match (RAG-based)
            PatternValidator(patterns=context.patterns).validate(code),
            
            # Layer 5: Backtest sandbox
            await SandboxBacktest(n_bars=100).run(code)
        ]
        
        return GuardResult(all(checks), failed_layers=[...])
```

### 2.3 Backtest Engine

```python
class BacktestValidator:
    """
    Strategy performance validation with Trinity Score
    """
    
    async def validate(self, code: str, regimes: list) -> BacktestResult:
        results = []
        for regime in regimes:
            result = await self.run_backtest(code, regime)
            results.append(result)
        
        # Aggregate metrics
        return BacktestResult(
            trinity_score=self._calculate_trinity(results),
            sharpe=statistics.mean([r.sharpe for r in results]),
            win_rate=statistics.mean([r.win_rate for r in results]),
            mdd=min([r.mdd for r in results]),
            regime_robustness=self._calculate_regime_std(results)
        )
```

---

## 3. Integration Points

### 3.1 Data → AI Contract

```json
{
  "version": "2.1.0",
  "timestamp": "2025-04-11T14:30:00Z",
  "validation": {
    "passed": true,
    "checks": ["finite", "zscore", "freshness", "completeness"]
  },
  "regime": {
    "type": "Trending_Normal",
    "confidence": 0.87,
    "features_used": ["adx", "vol_percentile"]
  },
  "market_data": {
    "tabular_format": "| Metric | Value | Z-Score |\n| price | 69450 | +0.12 |",
    "raw_features": {...}
  }
}
```

### 3.2 AI → Backtest Contract

```json
{
  "generated_code": "class StrategyV2_15(StrategyInterface): ...",
  "context": {
    "version": "2.1.0",
    "regime": "Trending_Normal",
    "rag_patterns": ["pattern_id_1", "pattern_id_2"]
  },
  "guard_result": {
    "passed": true,
    "validation_layers": ["syntax", "security", "semantic", "pattern", "sandbox"]
  }
}
```

---

## 4. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)
- [ ] P0: Feature Quality Gates (Analyst)
- [ ] P0: Data Pipeline with validation

### Phase 2: Intelligence (Weeks 3-4)
- [ ] P1: Online Regime Detection (Analyst)
- [ ] P1: Context Assembly v2.1 (AI)
- [ ] P1: RAG KB with filters

### Phase 3: Validation (Weeks 5-6)
- [ ] P2: Hallucination Guard v2
- [ ] P2: Context Versioning
- [ ] P2: Enhanced Backtest with regime testing

### Phase 4: Optimization (Weeks 7-8)
- [ ] P3: Self-Correction Loop
- [ ] P3: Knowledge Graph integration
- [ ] P3: Meta-learning from evolution history

---

## 5. Success Metrics

| Metric | Current | Target v2.0 |
|--------|---------|-------------|
| Strategy Generation Success Rate | 60% | 85% |
| Hallucination Rate | ~30% | <5% |
| Avg Trinity Score | 120 | 150 |
| Regime Robustness (Sharpe std) | 0.8 | 0.4 |
| Context Assembly Time | N/A | <500ms |
| RAG Retrieval Latency | N/A | <100ms |

---

## 6. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Data quality failure | Quality Gates with fallback to cached context |
| RAG retrieval failure | Fallback to static pattern library |
| LLM hallucination | Six-layer validation with sandbox |
| Regime misclassification | Confidence threshold + multi-regime testing |

---

*Prepared by: AI Expert*  
*With contributions from: Analyst Expert*  
*Awaiting: Trader Expert Risk/Validation input*
