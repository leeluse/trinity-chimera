### 2-4. RL Layer

**CryptoTradingEnv** (`rl/trading_env.py`)
- Gymnasium 표준 인터페이스
- Action: continuous [-1, 1] (포지션 비율)
- Observation: ML 신호 + regime + 시장 피처 + 포트폴리오 상태
- Reward: Sharpe / Sortino / PnL (선택)
- 수수료 + 슬리피지 내장

**train_rl.py**
- PPO (안정적, 병렬 env 지원) / SAC (샘플 효율)
- VecNormalize로 obs 정규화
- TensorBoard 로깅
- 최적 모델 자동 체크포인팅

