## 3. 에이전트 배틀 시스템

### 3-1. 설계 철학

각 에이전트는 **고정된 페르소나와 세계관**을 가진다.
페르소나는 단순한 이름이 아니라 관찰 공간 구성 / 보상 함수 / 진입 철학에 직접 영향을 준다.
에이전트들은 공유 시장 데이터에서 **서로 다른 것을 보고** 서로 다른 결정을 내린다.
Arbiter가 주기적으로 성과를 심판하고 **자본을 재배분**한다.

### 3-2. 에이전트 페르소나

#### Agent 1 — MOMENTUM HUNTER `agents/momentum_hunter.py`
```
페르소나  : 추세만 먹는다. 횡보는 존재하지 않는다.
알고리즘  : PPO + LSTM (시계열 메모리 활용)
진입 조건 : regime=bull + ML confidence ≥ 0.55 + 모멘텀 피처 강세
청산 조건 : 모멘텀 반전 또는 regime 전환
포지션    : 롱 전용 (베어장 진입 금지)
보상 함수  : PnL 기반 (Sharpe 불필요 — 추세 구간에서 공격적으로)
고유 피처  : ROC, ADX, 52주 신고가 대비 위치
```

#### Agent 2 — MEAN REVERTER `agents/mean_reverter.py`
```
페르소나  : 모두가 패닉셀 할 때 산다. 고점에서 판다.
알고리즘  : SAC + ATR 기반 동적 장벽
진입 조건 : 과매도 (RSI < 30) + 볼린저 하단 이탈 + 거래량 급증
청산 조건 : 평균 회귀 완료 (RSI > 60) 또는 SL
포지션    : 양방향 (횡보/베어장 특화)
보상 함수  : Sortino (하방 변동성만 패널티)
고유 피처  : BB deviation, RSI divergence, 펀딩비 극단값
```
#### Agent 3 — MACRO TRADER `agents/macro_trader.py`
```
페르소나  : 시장을 크게 본다. 단기 노이즈는 무시한다.
알고리즘  : PPO + HMM 상태를 1차 필터로 사용
진입 조건 : regime 전환 감지 직후 방향 포지션
청산 조건 : regime 재전환 또는 max_hold 도달
포지션    : 양방향, 낮은 빈도 (주 1-3회)
보상 함수  : Sharpe (장기 리스크 조정 수익 극대화)
고유 피처  : 미결제약정 변화, 공포탐욕지수, 4h/1d 멀티타임프레임
```

#### Agent 4 — CHAOS AGENT `agents/chaos_agent.py`
```
페르소나  : 예측 불가능성이 무기다. 시장이 내 패턴을 학습하지 못하게 한다.
알고리즘  : SAC + 노이즈 주입 (action에 epsilon 확률로 랜덤 교란)
진입 조건 : ML 신호 역방향 진입도 허용 (contrarian)
청산 조건 : RL이 학습한 최적 청산 시점
포지션    : 양방향, 소규모 다수 포지션
보상 함수  : PnL - 다른 에이전트와의 상관관계 패널티
            (다양성 유지가 전략의 핵심)
고유 피처  : 다른 에이전트들의 현재 포지션 방향 (역방향 진입 참고)
```



### 3-4. 에이전트 자가 전략 생성 (Self-Strategy Generation)

각 에이전트는 주기적으로 LLM을 호출해 **자신의 전략 파라미터를 스스로 제안**한다.
제안된 파라미터는 샌드박스 백테스트를 거쳐 채택 여부가 결정된다.

```python
# agents/base_agent.py → self_improve() 메서드
class BaseAgent:
    def self_improve(self, recent_performance: dict, regime: str) -> dict:
        """
        LLM에게 최근 성과와 regime을 주고
        하이퍼파라미터 조정안을 제안받는다.
        """
        prompt = f"""
        당신은 {self.persona} 페르소나를 가진 트레이딩 에이전트입니다.
        최근 7일 성과: {recent_performance}
        현재 시장 regime: {regime}

        당신의 전략 파라미터를 조정하세요. 페르소나를 절대 바꾸지 마세요.
        현재 파라미터: {self.params}

        출력 (JSON):
        {{
          "params": {{...}},
          "rationale": "...",
          "expected_improvement": "..."
        }}
        """
        # Claude API 호출 → 파라미터 제안 → 샌드박스 검증 → 채택/기각
```
**자가 개선 사이클:**
```
매 14일:
  1. 에이전트가 LLM에 파라미터 조정 요청
  2. 제안된 파라미터로 최근 30일 데이터 백테스트
  3. Sharpe 개선 ≥ 0.1이면 채택, 아니면 기각
  4. 채택 이력 저장 (agents/history/{agent_name}/)
  5. Arbiter에게 변경 사항 통보
```