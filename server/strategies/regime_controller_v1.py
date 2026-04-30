import numpy as np
import pandas as pd

# NOTE:
# This strategy is a "controller" that blends existing strategies depending on
# higher-timeframe regime classification.
#
# - five_sig: pivot/divergence based (can have pivot lookahead characteristics)
#             -> we delay it a bit to reduce leakage risk.
# - attack_sig: trend/attack style (long-biased).
from server.strategies.robust_signal_v2_optimized import generate_signal as generate_five_signal
from server.strategies.quant_trend_engine_v3 import generate_signal as generate_attack_signal


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h = df["high"]
    l = df["low"]
    c = df["close"]
    pc = c.shift(1)

    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(span=n, adjust=False).mean()


def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    # Assumes df index is a DatetimeIndex.
    return (
        df.resample(rule)
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        .dropna()
    )


def classify_regime(df: pd.DataFrame) -> pd.DataFrame:
    c = df["close"]

    fast = ema(c, 30)
    mid = ema(c, 80)
    slow = ema(c, 150)

    up_structure = (fast > mid) & (mid > slow)
    down_structure = (fast < mid) & (mid < slow)

    slope = (slow - slow.shift(10)) / slow.shift(10).replace(0, np.nan)

    path = c.diff().abs().rolling(20).sum()
    efficiency = (c - c.shift(20)).abs() / (path + 1e-9)

    atr_pct = atr(df, 14) / c.replace(0, np.nan)
    vol_rank = atr_pct.rolling(200).rank(pct=True)

    up_score = (
        up_structure.astype(float)
        + (slope > 0.0002).astype(float)
        + (efficiency > 0.35).astype(float)
        + (vol_rank < 0.75).astype(float)
    )

    down_score = (
        down_structure.astype(float)
        + (slope < -0.0002).astype(float)
        + (efficiency > 0.35).astype(float)
        + (vol_rank < 0.75).astype(float)
    )

    up_strength = ((up_score - 1) / 3).clip(0, 1)
    down_strength = ((down_score - 1) / 3).clip(0, 1)

    regime = pd.Series("UNCERTAIN", index=df.index, dtype="object")

    regime[(up_score >= 3) & (vol_rank < 0.70)] = "TREND_UP_LOW_VOL"
    regime[(up_score >= 3) & (vol_rank >= 0.70)] = "TREND_UP_HIGH_VOL"

    regime[(down_score >= 3) & (vol_rank < 0.70)] = "TREND_DOWN_LOW_VOL"
    regime[(down_score >= 3) & (vol_rank >= 0.70)] = "TREND_DOWN_HIGH_VOL"

    range_cond = (up_score < 3) & (down_score < 3) & (efficiency < 0.35)
    regime[range_cond & (vol_rank < 0.70)] = "RANGE_LOW_VOL"
    regime[range_cond & (vol_rank >= 0.70)] = "RANGE_HIGH_VOL"

    # Avoid future leak: use last fully completed bar (shift by 1 HTF bar).
    return pd.DataFrame(
        {
            "regime": regime.shift(1).fillna("UNCERTAIN"),
            "up_strength": up_strength.shift(1).fillna(0.0),
            "down_strength": down_strength.shift(1).fillna(0.0),
            "vol_rank": vol_rank.shift(1).fillna(0.5),
        },
        index=df.index,
    )


def _prep_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).lower() for c in out.columns]

    # Backtester expects time-ascending order.
    out = out.sort_index()
    out = out[~out.index.duplicated(keep="last")]

    required = ["open", "high", "low", "close", "volume"]
    for col in required:
        if col not in out.columns:
            raise ValueError(f"Missing required column: {col}")
        out[col] = pd.to_numeric(out[col], errors="coerce")

    out = out.dropna(subset=required)
    return out


def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:
    """
    Regime Controller v1

    - 4H: macro regime
    - 1H: confirmation / strength gating
    - base timeframe (test_df): signal emission
    """
    df = _prep_ohlcv(test_df)

    # Need enough history for 200-bar vol_rank on HTFs + EMAs.
    if len(df) < 800:
        return pd.Series(0, index=test_df.index, dtype=int)

    # 1) Run underlying strategies on base timeframe
    five_sig = generate_five_signal(train_df, df).astype(float)
    # Pivot-based strategies can leak due to using future bars to confirm pivots.
    # Delay the output to reduce leakage impact in a bar-by-bar backtester.
    five_sig = five_sig.shift(8).fillna(0).astype(int).clip(-1, 1)

    attack_sig = generate_attack_signal(train_df, df).fillna(0).astype(int).clip(-1, 1)

    # 2) Regime computation (HTF)
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("Index must be a DatetimeIndex for resampling.")

    df_1h = resample_ohlcv(df, "1h")
    df_4h = resample_ohlcv(df, "4h")

    reg_1h = classify_regime(df_1h).reindex(df.index, method="ffill")
    reg_4h = classify_regime(df_4h).reindex(df.index, method="ffill")

    final = pd.Series(0, index=df.index, dtype=int)

    # 3) Controller
    for i in range(len(df)):
        r4 = reg_4h["regime"].iloc[i]
        r1 = reg_1h["regime"].iloc[i]

        up_strength = min(float(reg_4h["up_strength"].iloc[i]), float(reg_1h["up_strength"].iloc[i]))
        down_strength = min(float(reg_4h["down_strength"].iloc[i]), float(reg_1h["down_strength"].iloc[i]))
        vol_rank = float(reg_4h["vol_rank"].iloc[i])

        sig = 0

        if r4 == "TREND_UP_LOW_VOL":
            if attack_sig.iloc[i] == 1 and up_strength >= 0.35:
                sig = 1

        elif r4 == "TREND_UP_HIGH_VOL":
            if (
                r1 in ["TREND_UP_LOW_VOL", "TREND_UP_HIGH_VOL"]
                and attack_sig.iloc[i] == 1
                and up_strength >= 0.55
                and vol_rank < 0.90
            ):
                sig = 1

        elif r4 == "TREND_DOWN_LOW_VOL":
            if five_sig.iloc[i] == -1 and down_strength >= 0.35:
                sig = -1

        elif r4 == "TREND_DOWN_HIGH_VOL":
            if five_sig.iloc[i] == -1 and down_strength >= 0.55 and vol_rank < 0.90:
                sig = -1

        elif r4 == "RANGE_LOW_VOL":
            if r1 in ["RANGE_LOW_VOL", "UNCERTAIN"]:
                sig = int(five_sig.iloc[i])

        elif r4 == "RANGE_HIGH_VOL":
            sig = 0

        else:
            sig = 0

        # Final noise cut
        if vol_rank >= 0.92:
            sig = 0

        final.iloc[i] = sig

    return final.reindex(test_df.index).fillna(0).astype(int).clip(-1, 1)

