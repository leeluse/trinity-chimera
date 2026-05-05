# Strategy Code Spec

진화(Evolution)·채팅(Chat) 두 파이프라인 모두에서 LLM이 생성하는 전략 코드의 규격을 정의합니다.

## 필수 시그니처

```python
def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:
```

| 인자 | 타입 | 설명 |
|---|---|---|
| `train_df` | `pd.DataFrame` | 파라미터 학습·최적화용 과거 데이터 |
| `test_df` | `pd.DataFrame` | 실제 신호 생성 대상 데이터 |
| 반환 | `pd.Series` | `test_df.index`와 동일한 인덱스, 값: 1(롱) / -1(숏) / 0(관망) |

## 데이터 스키마

`train_df`, `test_df` 모두 동일한 구조:

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `open` | float | 시가 |
| `high` | float | 고가 |
| `low` | float | 저가 |
| `close` | float | 종가 |
| `volume` | float | 거래량 |
| index | `DatetimeIndex` | 봉 시각 (1h 기준) |

행 수: quick 모드 약 1,080개(45일 × 24h), full 모드 약 4,320개(180일 × 24h)

## 허용 라이브러리

```python
import numpy as np
import pandas as pd
```

> **금지**: `ta`, `talib`, `scipy`, `sklearn`, `torch`, `requests` 등 외부 패키지 전부

## 최소 거래 수

- `quick_gate`: 10건 이상 (Quick Gate 통과 기준)
- `hard_gate` 채택: 30건 이상
- **진입 조건이 너무 엄격하면 0건 → 즉시 폐기**

## 지표 구현 레시피

```python
close = test_df['close']
high  = test_df['high']
low   = test_df['low']
vol   = test_df['volume']

# ── EMA ──────────────────────────────────────────
ema_fast = close.ewm(span=12, adjust=False).mean()
ema_slow = close.ewm(span=26, adjust=False).mean()

# ── SMA ──────────────────────────────────────────
sma20 = close.rolling(20).mean()

# ── RSI ──────────────────────────────────────────
d = close.diff()
gain = d.clip(lower=0).rolling(14).mean()
loss = (-d.clip(upper=0).rolling(14).mean()).replace(0, 1e-9)
rsi = 100 - 100 / (1 + gain / loss)

# ── Bollinger Bands ───────────────────────────────
std20   = close.rolling(20).std()
upper_bb = sma20 + 2 * std20
lower_bb = sma20 - 2 * std20

# ── ATR ──────────────────────────────────────────
tr  = pd.concat([(high - low),
                 (high - close.shift()).abs(),
                 (low  - close.shift()).abs()], axis=1).max(axis=1)
atr = tr.ewm(span=14, adjust=False).mean()

# ── MACD ─────────────────────────────────────────
macd     = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
sig_line = macd.ewm(span=9, adjust=False).mean()
hist     = macd - sig_line

# ── Stochastic %K ────────────────────────────────
lowest  = low.rolling(14).min()
highest = high.rolling(14).max()
stoch_k = 100 * (close - lowest) / (highest - lowest).replace(0, 1e-9)

# ── 거래량 비율 ────────────────────────────────────
vol_ratio = vol / vol.rolling(20).mean()
```

## 완성 예시 (EMA 크로스오버 + RSI 필터)

```python
import numpy as np
import pandas as pd

def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:
    close = test_df['close']

    ema_fast = close.ewm(span=12, adjust=False).mean()
    ema_slow = close.ewm(span=26, adjust=False).mean()

    d    = close.diff()
    gain = d.clip(lower=0).rolling(14).mean()
    loss = (-d.clip(upper=0).rolling(14).mean()).replace(0, 1e-9)
    rsi  = 100 - 100 / (1 + gain / loss)

    sig = pd.Series(0, index=test_df.index, dtype=int)
    sig[(ema_fast > ema_slow) & (rsi < 65)] = 1
    sig[(ema_fast < ema_slow) & (rsi > 35)] = -1

    return sig.fillna(0).astype(int)
```

## 내부 처리 흐름

`strategy_from_code()` (`server/modules/backtest/backtest_engine.py`) 가 코드를 파싱하여 실행 가능한 함수로 변환한다.

```
generate_signal 함수 존재?
  YES → 벡터화 경로 (1순위) ← 권장
  NO  → 클래스 탐색 (2순위) → 행별 루프 (느림·오류 多)
```

**항상 함수 방식으로 생성해야 한다.**

## 보안 제약 (`StrategyLoader.validate_code`)

AST 정적 분석으로 아래를 차단:
- 금지 모듈: `os`, `sys`, `subprocess`, `socket`, `pickle`, `threading` 등
- 금지 함수: `open`, `eval`, `exec`, `__import__`
- 허용 모듈 접두어: `pandas`, `numpy`, `math`, `typing`, `collections`, `datetime`, `server.shared.market.strategy_interface`

## 관련 파일

| 파일 | 역할 |
|---|---|
| `server/modules/evolution/llm.py` | 진화 LLM 프롬프트 조립 |
| `server/modules/chat/prompts.py` | 채팅 코드 프롬프트 (`CODE_PROMPT_TEMPLATE`) |
| `server/modules/backtest/backtest_engine.py` | `strategy_from_code()` — 코드→함수 변환 |
| `server/shared/market/strategy_loader.py` | 보안 검증 + 클래스 호환 레이어 |
| `server/shared/market/strategy_interface.py` | `StrategyInterface` / `CompatStrategyBase` 정의 |
