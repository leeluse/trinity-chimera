# PROJECT.md — AI Trading System

> 페르소나를 가진 자율 에이전트들이 각자 전략을 스스로 생성하고,
> 서로 경쟁하며 자본을 배분받는 멀티-에이전트 트레이딩 시스템.

---

## 목차

1. [시스템 전체 구조](#1-시스템-전체-구조)
2. [레이어별 설명](#2-레이어별-설명)
3. [디렉토리 구조](#3-디렉토리-구조)
4. [구현 로드맵](#4-구현-로드맵)
5. [설계 결정 기록](#5-설계-결정-기록)

---

## 1. 시스템 전체 구조

```
┌─────────────────────────────────────────────────────────────────┐
│                        MARKET DATA LAYER                        │
│   CCXT (OHLCV · 오더북 · 펀딩비 · 미결제약정)  ──→  Feature Store  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                      PERCEPTION LAYER                           │
│   HMM Regime Classifier  ──→  bull / sideways / bear           │
│   Triple Barrier Labeler ──→  +1 / 0 / -1 + sample weights     │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                      SIGNAL LAYER (FreqAI)                      │
│   LightGBM  ──→  방향 확률 + 신뢰도                               │
│   (regime-conditioned, isotonic calibration)                    │
└──────────────────────────────┬──────────────────────────────────┘
                               │  ML signal (p_long, p_short, confidence)
                               │  + regime (bull/sideways/bear)
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   AGENT BATTLE SYSTEM  ◄── 신규                 │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ MOMENTUM │  │  MEAN    │  │  MACRO   │  │  CHAOS   │       │
│  │  HUNTER  │  │ REVERTER │  │  TRADER  │  │  AGENT   │       │
│  │          │  │          │  │          │  │          │       │
│  │ PPO+LSTM │  │ SAC+ATR  │  │HMM-first │  │ Contrari │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
│       │             │              │              │             │
│       └─────────────┴──────────────┴──────────────┘             │
│                             │                                   │
│                    ┌────────▼────────┐                          │
│                    │  배틀 오케스트레이터  │                          │
│                    │  성과 심판 +       │                          │
│                    │  자본 재배분       │                          │
│                    └────────┬────────┘                          │
└─────────────────────────────┼───────────────────────────────────┘
                              │  최종 포지션 + 사이즈
┌─────────────────────────────▼───────────────────────────────────┐
│                     EXECUTION LAYER                             │
│         Freqtrade  ──→  CCXT  ──→  Binance / Bybit              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 레이어별 설명

### 2-1. Market Data Layer

| 컴포넌트 | 소스 | 주기 |
|---|---|---|
| OHLCV | CCXT | 1m / 1h / 4h |
| 오더북 스냅샷 | CCXT L2 | 실시간 |
| 펀딩비 | Binance / Bybit | 8h |
| 미결제약정 (OI) | Binance Futures | 1h |
| 공포탐욕지수 | Alternative.me API | 1d |


---

## 3. 디렉토리 구조

```
ai_trading/
│
├── core/                          # 공유 퍼셉션 레이어
│   ├── __init__.py
│   ├── hmm_regime.py              #  — HMM 시장 regime 분류
│   └── triple_barrier.py          #  — Triple Barrier 레이블
│
├── freqai/                        # FreqAI 커스텀 모델
│   └── lgbm_model.py              #  — LightGBM + 캘리브레이션
│
├── rl/                            # RL 인프라
│   ├── __init__.py
│   ├── trading_env.py             #  — Gymnasium 환경
│   └── train_rl.py                #  — PPO/SAC 학습 스크립트
│
├── agents/                        # ✅ — 에이전트 배틀 시스템
│   ├── __init__.py
│   ├── base_agent.py              # ✅ 에이전트 추상 기반 클래스
│   │                              #   - RL 모델 로드/저장
│   │                              #   - self_improve() (LLM 호출)
│   │                              #   - 성과 메트릭 계산
│   │
│   ├── momentum_hunter.py         # ✅ 추세 추종 에이전트
│   ├── mean_reverter.py           # ✅ 평균회귀 에이전트
│   ├── macro_trader.py            # ✅ 매크로/regime 기반 에이전트
│   ├── chaos_agent.py             # ✅ 반상관 contrarian 에이전트
│   │
│   └── history/                   # 에이전트 자가 개선 이력
│       ├── momentum_hunter/
│       ├── mean_reverter/
│       ├── macro_trader/
│       └── chaos_agent/
│
├── battle/                        # ✅ — 배틀 오케스트레이션
│   ├── __init__.py
│   ├── arena.py                   # ✅ 배틀 실행 루프
│   │                              #   - 에이전트 초기화
│   │                              #   - 주기적 재배분 트리거
│   │                              #   - 충돌 해소 (가중 투표)
│   │                              #   - 최종 주문 생성
│   │                              #   - 성과 심판 + 자본 재배분
│   │
│   ├── portfolio.py               # ✅ 가상 포트폴리오 + 자본 추적
│   └── logger.py                  # 배틀 이력 기록 (JSON + SQLite)
│
├── AITradingStrategy.py           #  — Freqtrade 단일 전략
│                                  #    (에이전트 배틀 이전 버전)
│
├── AIBattleStrategy.py            #  — 배틀 시스템 통합 전략
│                                  #    Freqtrade hook → Arena 호출
│
├── data/                          # 로컬 캐시 (gitignore)
│   ├── ohlcv/
│   ├── orderbook/
│   └── features/
│
├── models/                        # 학습된 모델 저장
│   ├── rl/
│   │   ├── momentum_hunter/
│   │   ├── mean_reverter/
│   │   ├── macro_trader/
│   │   └── chaos_agent/
│   └── lgbm/
│
├── logs/                          # 실행 로그
│   ├── battle/
│   └── rl/
│
├── tests/                         # 🔲 미구현
│   ├── test_hmm.py
│   ├── test_triple_barrier.py
│   └── test_agents.py
│
├── notebooks/                     # 분석 노트북
│   ├── 01_regime_analysis.ipynb
│   ├── 02_label_quality.ipynb
│   └── 03_agent_battle_replay.ipynb
│
├── PROJECT.md                     # ← 이 파일
├── README.md                      # 빠른 시작 가이드
└── requirements.txt
```

---

### 4. 백테스트 흐름

```
1. 데이터 준비
   raw OHLCV
     └→ build_hmm_features()     → HMM 학습/예측 → regime Series
     └→ TripleBarrier.label()     → label / weight DataFrame
     └→ feature_engineering_*()  → LightGBM 피처 행렬

2. ML 학습 (FreqAI walk-forward)
   피처 + 레이블 + weight
     └→ LightGBMRegimeModel.fit() → 모델 저장
     └→ predict()                 → p_long, p_short, confidence

3. 에이전트 별 RL 학습
   ML 신호 + regime + OHLCV
     └→ CryptoTradingEnv(agent_config)
     └→ PPO/SAC.learn()
     └→ models/rl/{agent_name}/best_model.zip

4. 배틀 백테스트
   Arena.run_backtest()
     └→ 각 에이전트 → action ([-1,1])
     └→ 자본 가중 투표 → net_signal
     └→ 수수료/슬리피지 → PnL
     └→ Arbiter.reallocate() (매 7일)
     └→ battle/logs/ 저장
```

### 5. 라이브 트레이딩 흐름

```
매 캔들 마감 (1h):
  1. CCXT → 신규 OHLCV + 오더북
  2. RegimeClassifier.predict_live() → regime
  3. FreqAI 추론 → p_long, p_short, confidence
  4. Arena.step()
       └→ 각 에이전트 .act(obs) → action
       └→ 충돌 해소 → net_action
       └→ custom_stake_amount() → 포지션 크기
  5. Freqtrade → CCXT → 거래소 주문

매주 월요일 00:00 UTC:
  6. 배틀 오케스트레이터.weekly_review()
       └→ 성과 집계 → 재배분 결정
       └→ 신규 allocation → Arena 반영

매 14일:
  7. 각 에이전트 .self_improve()
       └→ Claude API 파라미터 제안
       └→ 샌드박스 백테스트 → 채택/기각
```

---

## 6. 구현 로드맵

### Phase 1 — 완료 ✅ (2026-04-05)
기반 인프라 전체 구축

- [x] HMM Regime Classifier (`core/hmm_regime.py`) - 15개 테스트 통과
- [x] Triple Barrier Labeler (`core/triple_barrier.py`) - 완전 구현
- [ ] LightGBM FreqAI Model (`freqai/lgbm_model.py`) - Phase 2로 이동
- [x] Gymnasium Trading Env (`rl/trading_env.py`) - 26개 테스트 통과
- [x] PPO/SAC Training Script (`rl/train_rl.py`) - 연구 완료
- [ ] Freqtrade Strategy (`AITradingStrategy.py`) - Phase 2로 이동

---

### Phase 2 — 다음 🔲
에이전트 배틀 시스템 골격

**목표:** 4개 에이전트가 각자의 RL 모델로 독립적으로 행동하고
배틀 오케스트레이터가 자본을 재배분하는 배틀 루프 완성.

- [ ] `agents/base_agent.py` — 공통 인터페이스
  - `__init__(config, rl_model_path)`
  - `act(observation) → float`  (-1 ~ 1)
  - `compute_metrics(portfolio_history) → dict`
  - `save() / load()`

- [ ] 4개 에이전트 구현
  - `agents/momentum_hunter.py`
  - `agents/mean_reverter.py`
  - `agents/macro_trader.py`
  - `agents/chaos_agent.py`
  - 각자 고유 obs 빌더 + 보상 함수 + RL 학습 설정

- [ ] `battle/arena.py` — 배틀 루프
  - 에이전트 초기화 + 자본 배분 상태 관리
  - `step(market_obs) → final_action`
  - 가중 투표 충돌 해소
  - 매 N스텝 재배분 트리거

- [ ] `battle/portfolio.py` — 자본 추적
  - 에이전트별 가상 계좌
  - 전체 포트폴리오 PnL 집계
  - Sharpe + Drawdown 기반 점수 계산
  - 배분 규칙 하드코딩 (min 5%, max 50%)

- [ ] 배틀 백테스트 실행 + 결과 분석 노트북

---

### Phase 3 — 이후 🔲
자가 전략 생성

**목표:** 에이전트들이 스스로 파라미터를 조정한다.

- [ ] `agents/base_agent.py` → `self_improve()` 메서드
  - 파라미터 제안
  - 샌드박스 백테스트 자동 실행
  - 채택/기각 로직

- [ ] `AIBattleStrategy.py`
  - Freqtrade hook → Arena 연결
  - `populate_entry_trend` → `arena.step()` 호출
  - `custom_stake_amount` → 배분 가중 포지션 크기

- [ ] Chaos Agent 다양성 보상 구현
  - 다른 에이전트 포지션을 obs에 포함
  - 상관관계 패널티 보상 함수

---

### Phase 4 — 장기 🔲
시스템 강화 및 확장

- [ ] 에이전트 추가 생성 인터페이스 (새 페르소나 손쉽게 추가)
- [ ] 에이전트 은퇴/교체 메커니즘 (장기 언더퍼폼 시 신규 에이전트로 대체)
- [ ] 멀티 심볼 확장 (BTC, ETH, SOL 동시 운용)
- [ ] 웹 대시보드 (에이전트별 실시간 PnL, 배분 시각화)
- [ ] 거래소 시뮬레이터 고도화 (부분 체결, 펀딩비 실제 반영)

---

## 7. 설계 결정 기록

### ADR-001 에이전트 알고리즘으로 PPO vs SAC

**결정:** 추세 에이전트(Momentum, Macro)는 PPO, 역추세 에이전트(Reverter, Chaos)는 SAC.

**근거:**
PPO는 on-policy라 안정적이지만 샘플이 많이 필요하다.
추세장은 지속성이 있어 같은 경험을 반복 학습해도 괜찮다.
SAC는 replay buffer를 써서 희귀한 반전 시그널을 재활용하기 유리하다.
Mean Reversion 기회는 드물기 때문에 SAC가 더 적합하다.

---

### ADR-002 배틀 오케스트레이터의 재배분 방식

**결정:** 규칙 기반 재배분 시스템 사용.

**근거:**
단순 Sharpe 기반 재배분은 구현이 쉽고 디버깅이 쉽다.
규칙 기반 시스템은 투명하고 예측 가능하며 안정적이다.
성능 기반 자동 재배분으로 에이전트 간 경쟁을 유도한다.

---

### ADR-003 Chaos Agent의 존재 이유

**결정:** Chaos Agent를 항상 최소 10% 유지.

**근거:**
모든 에이전트가 같은 방향을 볼 경우 전체 포트폴리오가 단일 리스크에 노출된다.
Chaos Agent는 의도적으로 다른 에이전트와 반상관 포지션을 취해
포트폴리오 전체의 분산을 강제로 유지하는 보험 역할을 한다.
실제로 시장이 예측 불가능한 방향으로 움직일 때 Chaos Agent가 수익을 낼 수 있다.

---

### ADR-004 Triple Barrier에서 time-out weight를 0.3으로 설정

**결정:** TP/SL 히트 = weight 1.0, 시간 만료 = weight 0.3.

**근거:**
시간 장벽에 걸린 바는 방향성이 없었다는 의미이므로 노이즈가 많다.
weight를 낮춰 모델이 약한 신호에서 학습하는 비중을 줄인다.
0으로 완전히 제거하면 플랫 레이블이 부족해져 클래스 불균형이 심해진다.
0.3은 "약한 신호를 무시하지는 않되 큰 영향은 주지 않는다"는 절충점이다.

---

### ADR-005 에이전트 자가 개선 주기를 14일로 설정

**결정:** 7일 성과 평가 / 14일 파라미터 개선.

**근거:**
7일은 변동성이 심한 암호화폐 시장에서 통계적으로 유의미한 샘플을 얻기에 짧다.
그러나 14일이면 시장 regime이 크게 바뀔 수 있어 적응이 늦어진다.
절충안: 성과 평가(Arbiter)는 7일, 실제 파라미터 변경(self_improve)은 14일.
파라미터 변경은 반드시 샌드박스 백테스트를 통과해야 하므로
14일 주기가 너무 느리다고 판단되면 트리거 기반으로 바꿀 수 있다.


