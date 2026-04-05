# PPO (Proximal Policy Optimization) 연구 노트

## 1. PPO 기초 이론

### 1.1 정책 그래디언트 문제점
- **전통적 Policy Gradient**: 큰 업데이트시 정책이 급격히 변화 → 학습 불안정
- **TRPO 해결책**: KL divergence 제약 조건 사용하지만 복잡함
- **PPO 해결책**: 간단한 클리핑으로 안정적인 업데이트

### 1.2 PPO 핵심 공식

**Clipped Surrogate Objective:**
```
L(θ) = E[ min(r(θ) * A, clip(r(θ), 1-ε, 1+ε) * A) ]

where:
- r(θ) = π_θ(a|s) / π_old(a|s) (probability ratio)
- A = advantage function estimate
- ε = clip range (typically 0.2)
```

**Actor-Critic 구조:**
- **Actor**: 정책 네트워크 π(a|s) → 행동 선택
- **Critic**: 가치 네트워크 V(s) → 상태 가치 평가
- **Advantage 계산**: A(s,a) = Q(s,a) - V(s)

### 1.3 PPO 학습 과정

```python
1. Collect trajectories using current policy
2. Compute advantages using GAE (Generalized Advantage Estimation)
3. For K epochs:
   - Update policy with clipped objective
   - Update value function (MSE loss)
4. Repeat
```

## 2. stable-baselines3 PPO 구조

### 2.1 주요 하이퍼파라미터

| Parameter | Default | Description |
|-----------|---------|-------------|
| learning_rate | 3e-4 | Adam optimizer learning rate |
| n_steps | 2048 | Rollout buffer size |
| batch_size | 64 | Minibatch size for updates |
| n_epochs | 10 | Number of epoch per rollout |
| gamma | 0.99 | Discount factor |
| gae_lambda | 0.95 | GAE lambda for advantage estimation |
| clip_range | 0.2 | Clipping parameter ε |
| ent_coef | 0.0 | Entropy coefficient |
| vf_coef | 0.5 | Value function coefficient |
| max_grad_norm | 0.5 | Gradient clipping threshold |

### 2.2 네트워크 아키텍처

```python
# 기본 MLP (Multi-Layer Perceptron)
pi = [64, 64]  # Policy network
vf = [64, 64]  # Value network

# LSTM variant (for sequential data)
policy_kwargs = dict(
    net_arch=[dict(pi=[128, 128], vf=[128, 128])],
    lstm_hidden_size=64,
    n_lstm_layers=1
)
```

## 3. 학습 파이프라인 설계

### 3.1 데이터 흐름

```
┌─────────────┐    ┌─────────────┐    ┌──────────────┐
│ Market Data │───▶│ TradingEnv  │───▶│ PPO Learner  │
└─────────────┘    └─────────────┘    └──────────────┘
                          │                     │
                          ▼                     ▼
                   ┌─────────────┐        ┌─────────────┐
                   │ VecNormalize│        │  Callbacks  │
                   └─────────────┘        └─────────────┘
```

### 3.2 환경 래퍼 전략

```python
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

# 단일 환경 래핑
env = CryptoTradingEnv(config)
env = DummyVecEnv([lambda: env])
env = VecNormalize(env, norm_obs=True, norm_reward=True)
```

## 4. 모니터링 및 체크포인팅

### 4.1 TensorBoard 콜백

```python
from stable_baselines3.common.callbacks import EvalCallback

callback = EvalCallback(
    eval_env,
    best_model_save_path='./models/',
    log_path='./logs/',
    eval_freq=10000,
    deterministic=True,
    render=False
)
```

### 4.2 Checkpoint 콜백

```python
from stable_baselines3.common.callbacks import CheckpointCallback

checkpoint_callback = CheckpointCallback(
    save_freq=10000,
    save_path='./checkpoints/',
    name_prefix='ppo_trading'
)
```

### 4.3 Custom Callback (학습 추적)

```python
class TradingMetricsCallback(BaseCallback):
    def __init__(self, verbose=0):
        super().__init__(verbose)

    def _on_step(self) -> bool:
        # 매 스텝마다 호출
        return True

    def _on_rollout_end(self):
        # Rollout 종료 시 Sharpe ratio 등 계산
        pass
```

## 5. 트레이딩 특화 설정

### 5.1 Reward Shaping

**PnL 기반 보상:**
```python
reward = current_pnl - previous_pnl
```

**Sharpe Ratio 기반 보상:**
```python
reward = mean(returns) / std(returns)
```

**Sortino (하방 변동성만 페널티):**
```python
downside_returns = [r for r in returns if r < 0]
sortino = mean(returns) / std(downside_returns)
```

### 5.2 Action Space

```python
import gymnasium as gym

self.action_space = gym.spaces.Box(
    low=-1.0,
    high=1.0,
    shape=(1,),
    dtype=np.float32
)
# -1: Short, 0: Neutral, +1: Long
```

### 5.3 Observation Space

```python
self.observation_space = gym.spaces.Box(
    low=-np.inf,
    high=np.inf,
    shape=(n_features,),
    dtype=np.float32
)
```

## 6. 학습 스크립트 아키텍처

### 6.1 파일 구조

```
rl/
├── train_rl.py          # 메인 학습 스크립트
├── config.py            # 하이퍼파라미터 설정
├── callbacks.py         # 커스텀 콜백
├── trading_env.py       # Gymnasium 환경 (John)
└── utils.py            # 헬퍼 함수
```

### 6.2 학습 설정 (YAML 예시)

```yaml
# config/ppo_config.yaml
algorithm: PPO

env:
  name: CryptoTradingEnv
  window_size: 20
  initial_balance: 10000

ppo:
  learning_rate: 3e-4
  n_steps: 2048
  batch_size: 64
  n_epochs: 10
  gamma: 0.99
  gae_lambda: 0.95
  clip_range: 0.2
  ent_coef: 0.01
  vf_coef: 0.5
  max_grad_norm: 0.5

training:
  total_timesteps: 1000000
  eval_freq: 10000
  save_freq: 50000
  log_dir: ./logs
  checkpoint_dir: ./checkpoints
```

## 7. 안정화 기법

### 7.1 Gradient Clipping
```python
max_grad_norm = 0.5  # Gradient 폭주 방지
```

### 7.2 Reward Scaling
```python
# VecNormalize로 자동 보상 정규화
env = VecNormalize(env, norm_reward=True)
```

### 7.3 Exploration (Entropy)
```python
ent_coef = 0.01  # 충분한 탐험 유지
```

### 7.4 Learning Rate Annealing
```python
# 시간 경과에 따른 lr 감소
lr_schedule = linear_schedule(3e-4, 1e-6)
model = PPO(..., learning_rate=lr_schedule)
```

## 8. 최적화 전략

### 8.1 벡터화된 환경 (벡치 학습)
```python
from stable_baselines3.common.vec_env import SubprocVecEnv

envs = SubprocVecEnv([make_env(i) for i in range(8)])
```

### 8.2 Optuna 하이퍼파라미터 튜닝
```python
import optuna

def objective(trial):
    learning_rate = trial.suggest_float("learning_rate", 1e-5, 1e-3, log=True)
    clip_range = trial.suggest_float("clip_range", 0.1, 0.3)
    # ... 학습 및 평가
    return sharpe_ratio

study = optuna.create_study(direction="maximize")
study.optimize(objective, n_trials=100)
```

## 9. 검증 방법론

### 9.1 Walk-Forward Validation
```python
training_period = data[:split_date]
validation_period = data[split_date:next_split]
```

### 9.2 Backtest Metrics
- Sharpe Ratio
- Calmar Ratio
- Maximum Drawdown
- Win Rate
- Profit Factor

### 9.3 Overfitting Detection
- In-sample vs Out-of-sample performance gap
- Learning curve plateau
- Policy sensitivity analysis

## 참고 문헌

1. Schulman et al. (2017). "Proximal Policy Optimization Algorithms"
2. stable-baselines3 documentation
3. Sergey Ivanov. "Deep Reinforcement Learning for Trading"
