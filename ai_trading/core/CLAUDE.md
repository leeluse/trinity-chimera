
### 2-2. Perception Layer

**HMM Regime Classifier** (`core/hmm_regime.py`)
- 3-state Gaussian HMM (bull / sideways / bear)
- 입력: log_ret, realized_vol, abs_ret, volume_change, ATR
- Walk-forward 학습 (500봉 훈련 / 50봉 예측)
- 수익률 평균 기준 자동 레이블 정렬

**Triple Barrier Labeler** (`core/triple_barrier.py`)
- TP / SL / 시간 장벽 중 먼저 터치한 것으로 레이블
- ATR 기반 동적 장벽 크기 조정
- Regime별 다른 파라미터 (베어장 TP 더 좁게)
- time-out 레이블은 sample weight 0.3 (signal 품질 반영)

### Triple Barrier 구현 상세

**라벨 생성 로직:**
```python
label = 1   # Take Profit 장벽 먼저 터치 (상승)
label = -1  # Stop Loss 장벽 먼저 터치 (하락)
label = 0   # 시간 장벽 만료 (횡보/중립)
```

**장벽 계산 공식:**
```
TP_수준 = 현재_가격 × (1 + TP_배수 × ATR / 현재_가격)
SL_수준 = 현재_가격 × (1 - SL_배수 × ATR / 현재_가격)
시간_장벽 = 20개 봉 (최대 보유 기간)

기본 설정:
- TP multiplier: 2.0 (ATR의 2배)
- SL multiplier: 1.0 (ATR의 1배)
```

**샘플 가중치 계산:**
```python
weight = 1.0  if 장벽 == TP or SL (명확한 방향 신호)
weight = 0.3  if 장벽 == 시간 (불확실성 높음)
```

**주요 클래스:**
- `TripleBarrierLabeler`: 기본 라벨러
- `RegimeAwareBarrierLabeler`: HMM Regime과 통합된 라벨러
- `BarrierConfig`: 장벽 설정값
- `LabelOutput`: 단일 이벤트 라벨링 결과

**사용 예시:**
```python
from ai_trading.core import create_labeler, BarrierConfig

# 라벨러 생성
labeler = create_labeler(
    tp_multiplier=2.0,
    sl_multiplier=1.0,
    time_horizon=20,
    volatility_window=14
)

# OHLCV 데이터로 레이블 생성
result = labeler.label_events(ohlcv, events=event_times)

# 결과 접근
print(result.labels)        # {-1, 0, 1} 시리즈
print(result.returns)       # 실제 수익률
print(result.weights)       # 샘플 가중치
print(result.hold_times)    # 보유 기간

# 통계 분석
stats = labeler.get_barrier_stats(result)
print(f"TP rate: {stats['tp_rate']:.2%}")
print(f"SL rate: {stats['sl_rate']:.2%}")
print(f"Time expiry: {stats['time_rate']:.2%}")

# Regime 기반으로 라벨링
from ai_trading.core import RegimeAwareBarrierLabeler
regime_labeler = RegimeAwareBarrierLabeler(
    bull_adjustment=0.8,  # 상승장: 더 좁은 장벽
    bear_adjustment=1.2   # 하락장: 더 넓은 장벽
)
result = regime_labeler.label_with_regime(ohlcv, regime_series)
```

**Regime 조정 방식:**
- Bull regime: barrier × 0.8 (공격적 목표)
- Bear regime: barrier × 1.2 (보수적 목표)
- Neutral regime: barrier × 1.0 (표준)

**통합 포인트:**
- HMMRegimeClassifier의 출력을 regime_scores로 입력 가능
- 일반 Series 또는 DataFrame 입력 지원
- DatetimeIndex로 이벤트 시간 지정 가능
```python
# HMM Regime과 통합
regime_labeler = RegimeAwareBarrierLabeler()
regimes = hmm_classifier.predict(ohlcv)  # John이 개발한 HMM
features = triple_barrier.integrate_with_regime(features, regimes)
```