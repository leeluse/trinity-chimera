# Trading Strategy: Regime Bull

강세장(Bull Regime)에서 작동하는 세 가지 주요 전략의 정의와 목적입니다.

## 전략 01: Pullback-Reclaim
- **정의**: 눌림목 후 EMA20 회복 진입
- **목적**: 추세 중간 재진입용
- **상세**: 강한 상승 추세 중 일시적인 가격 조정(Pullback)이 발생했을 때, EMA20(20일 지수이동평균선)을 다시 상향 돌파하며 추세가 회복되는 지점을 포착합니다.

## 전략 02: BBWidth-MACD-OBV Breakout
- **정의**: 스퀴즈(Squeeze) 후 볼륨 브레이크아웃
- **목적**: 추세 초입 확장용
- **상세**: 볼린저 밴드의 폭이 좁아지는 스퀴즈 구간(변동성 축소)을 거친 후, MACD의 골든크로스와 OBV의 동반 상승을 동반하며 밴드 상단을 돌파하는 강력한 추세 전환 시점을 노립니다.

## 전략 03: RSI-ROC Momentum Acceleration
- **정의**: RSI 52~72 구간 + ROC10/ROC20 가속
- **목적**: 강한 직진 상승 구간용 (눌림/스퀴즈 없음)
- **상세**: RSI가 50 이상의 강세 구간(특히 52~72)에 진입하고, 가격 변화율(ROC)이 10봉/20봉 기준으로 동시에 가속화될 때 진입합니다. 조정이 거의 없는 수직 상승장에서 유용합니다.

---
**관련 코드**:
- `Bull_01_EMA_ADX_RSI_Pullback_NoLeakage.py`
- `Bull_02_BBWidth_MACD_OBV_Breakout_NoLeakage.py`
- `Bull_03_RSI_ROC_Momentum_Acceleration_v2.py`
