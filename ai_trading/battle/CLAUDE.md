### 3-3. 순수 자가 개선 시스템

#### 핵심 철학
**재분배 없이 각 에이전트가 자율적으로 진화**
- 각 에이전트는 고정된 자본으로 독립적으로 경쟁
- LLM은 자본 재분배가 아닌 **전략 개선**에 집중
- 진정한 자율적 진화 시스템

#### 경쟁 구조
```
총 가상 자본: 100 units (백테스트)

고정 배분 (재분배 없음):
  Momentum Hunter :  30 units
  Mean Reverter   :  30 units  
  Macro Trader    :  25 units
  Chaos Agent     :  15 units

각 에이전트는 고정 자본으로 독립적 트레이딩
성과는 개별 PnL로만 평가
```

#### 자가 개선 메커니즘
```python
# 에이전트별 자가 개선 사이클 (매 14일)
async def self_improve(self, recent_performance, regime, params):
    """LLM이 전략 파라미터 개선 제안"""
    
    proposal = await strategy_generator.generate_strategy(
        agent_name=self.name,
        persona=self.PERSONA,  # 고유한 페르소나 유지
        current_params=params,
        recent_performance=recent_performance,
        current_regime=regime
    )
    
    # 백테스팅 검증 후 파라미터 업데이트
    if self._validate_proposal(proposal):
        self.params = proposal.params
        logger.info(f"{self.name} 전략 개선 완료: {proposal.rationale}")
```

#### 에이전트 간 충돌 해소
동일 종목에 대해 에이전트들이 반대 포지션을 낼 경우:

```
자본 가중 투표:
  net_signal = Σ (agent_allocation × agent_action)

  예: Momentum(0.30) → +1.0 (롱)
      Mean Reverter(0.30) → -0.8 (숏)
      Macro(0.25) → +0.5 (약한 롱)
      Chaos(0.15) → -1.0 (숏)

  net = 0.30×1.0 + 0.30×(-0.8) + 0.25×0.5 + 0.15×(-1.0)
      = 0.30 - 0.24 + 0.125 - 0.15 = +0.035 → 소규모 롱
```

