### 3-3. 배틀 메커니즘

#### 경쟁 구조
```
총 가상 자본: 100 units (백테스트) / 실제 자본 일부 (라이브)

초기 배분:
  Momentum Hunter :  30 units
  Mean Reverter   :  30 units
  Macro Trader    :  25 units
  Chaos Agent     :  15 units

재배분 주기: 매 7일 (백테스트), 매주 월요일 00:00 UTC (라이브)
```


#### Arbiter — `agents/arbiter.py`

Arbiter는 LLM(Claude API)을 사용해 에이전트 성과를 **자연어로 분석**하고
재배분 결정을 내린다. 단순 수익률이 아닌 복합 지표로 심판.

```python
# Arbiter가 평가하는 지표
metrics = {
    "sharpe_7d":      float,   # 7일 샤프지수
    "max_drawdown":   float,   # 최대 낙폭
    "win_rate":       float,   # 승률
    "avg_hold_bars":  float,   # 평균 보유 봉수
    "regime_fit":     float,   # 현재 regime과 에이전트 궁합
    "diversity_score":float,   # 다른 에이전트와의 포지션 상관관계
    "overfit_score":  float,   # 최근 vs 이전 성과 괴리 (과적합 탐지)
}

# Arbiter 프롬프트 구조
prompt = f"""
당신은 퀀트 포트폴리오 매니저입니다.
현재 시장 regime: {regime}
각 에이전트의 7일 성과: {metrics_json}

다음을 판단하세요:
1. 현재 regime에서 어떤 에이전트가 가장 적합한가?
2. 어떤 에이전트가 과적합 징후를 보이는가?
3. 포트폴리오 다양성 관점에서 자본 배분을 어떻게 조정해야 하는가?

출력 형식 (JSON):
{{
  "allocation": {{"momentum": 0.30, "reverter": 0.25, "macro": 0.30, "chaos": 0.15}},
  "reasoning": "...",
  "warnings": ["..."]
}}
"""
```

#### 재배분 규칙
- 단일 에이전트 최대 배분: 50% (독점 방지)
- 단일 에이전트 최소 배분: 5% (퇴출 방지 — 회생 기회 보장)
- 7일 연속 Sharpe < -0.5인 에이전트: 강제 5%로 축소
- Chaos Agent는 항상 10-20% 유지 (다양성 보험)

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

