import numpy as np
import pandas as pd
from typing import Any, Dict


BEST_PARAMS: Dict[str, Any] = {
    "atr_len": 14,
    "rsi_len": 12,
    "rsi_ma_len": 3,
    "stoch_f_len": 3,
    "stoch_m_len": 14,
    "ema_trend": 150,
    "ema_fast": 20,
    "slope_lookback": 10,
    "stoch_oversold": 35,
    "stoch_overbought": 70,
    "slope_min": -0.005,      # 비율 기반: EMA 기울기 -0.5%까지 허용
    "rsi_max_entry": 60,
    "rsi_min_entry": 40,
    "long_trail_mult": 2.0,
    "short_trail_mult": 3.0,
    "tp_atr_mult": 1.5,
    "profit_lock_thresh": 0.02,
    "pivot_l": 5,
    "pivot_r": 2,             # 확인 지연 최소화
    "vol_ma_len": 20,
    "vol_surge_mult": 1.2,
    "use_ema_filter": True,   # EMA 필터: 트렌드 방향에서만 진입
    "use_vol_filter": False,
    "use_profit_lock": True,
    "warmup_bars": 150,
}


class PositionState:
    def __init__(self) -> None:
        self.active = False
        self.entry_price = None
        self.extreme = None
        self.tp_price = None


class RobustSignalEngineV2:
    def __init__(self, params: Dict[str, Any]):
        self.p = params
        self.long = PositionState()
        self.short = PositionState()

    @staticmethod
    def ema(s: pd.Series, n: int) -> pd.Series:
        return s.ewm(span=n, adjust=False).mean()

    @staticmethod
    def atr(h: pd.Series, l: pd.Series, c: pd.Series, n: int) -> pd.Series:
        pc = c.shift(1)
        tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
        return tr.ewm(span=n, adjust=False).mean()

    @staticmethod
    def rsi(c: pd.Series, n: int = 14) -> pd.Series:
        delta = c.diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1 / n).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1 / n).mean()
        rs = gain / (loss + 1e-9)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def stochastic(h: pd.Series, l: pd.Series, c: pd.Series, n: int) -> pd.Series:
        low = l.rolling(n).min()
        high = h.rolling(n).max()
        return 100 * (c - low) / (high - low + 1e-9)

    @staticmethod
    def pivot_low(s: pd.Series, left: int = 5, right: int = 2) -> pd.Series:
        # 미래 참조 제거: pivot_r봉 전 저점 후보가 좌우보다 낮은지 현재봉으로 확인
        pivot_bar = s.shift(right)
        left_ok   = s.shift(right + left) > pivot_bar
        right_ok  = s > pivot_bar
        return left_ok & right_ok

    @staticmethod
    def pivot_high(s: pd.Series, left: int = 5, right: int = 2) -> pd.Series:
        pivot_bar = s.shift(right)
        left_ok   = s.shift(right + left) < pivot_bar
        right_ok  = s < pivot_bar
        return left_ok & right_ok

    def divergence(self, c: pd.Series, rsi: pd.Series):
        pl = self.pivot_low(c, self.p["pivot_l"], self.p["pivot_r"])
        ph = self.pivot_high(c, self.p["pivot_l"], self.p["pivot_r"])

        hidden_bull = pd.Series(False, index=c.index)
        hidden_bear = pd.Series(False, index=c.index)
        reg_bull = pd.Series(False, index=c.index)
        reg_bear = pd.Series(False, index=c.index)

        last_low = None
        last_high = None

        for i in range(len(c)):
            if pl.iloc[i]:
                if last_low is not None:
                    if c.iloc[i] > c.iloc[last_low] and rsi.iloc[i] < rsi.iloc[last_low]:
                        hidden_bull.iloc[i] = True
                    if c.iloc[i] < c.iloc[last_low] and rsi.iloc[i] > rsi.iloc[last_low]:
                        reg_bull.iloc[i] = True
                last_low = i

            if ph.iloc[i]:
                if last_high is not None:
                    if c.iloc[i] < c.iloc[last_high] and rsi.iloc[i] > rsi.iloc[last_high]:
                        hidden_bear.iloc[i] = True
                    if c.iloc[i] > c.iloc[last_high] and rsi.iloc[i] < rsi.iloc[last_high]:
                        reg_bear.iloc[i] = True
                last_high = i

        return hidden_bull, hidden_bear, reg_bull, reg_bear

    def run(self, df: pd.DataFrame) -> pd.Series:
        c = df["close"].astype(float)
        h = df["high"].astype(float)
        l = df["low"].astype(float)
        v = df["volume"].astype(float)

        atr = self.atr(h, l, c, self.p["atr_len"])
        rsi = self.rsi(c, self.p["rsi_len"])
        stoch_f = self.stochastic(h, l, c, self.p["stoch_f_len"])
        stoch_m = self.stochastic(h, l, c, self.p["stoch_m_len"])
        ema_trend = self.ema(c, self.p["ema_trend"])
        # 비율 기반 slope (가격 스케일 불변)
        slope = (ema_trend - ema_trend.shift(self.p["slope_lookback"])) / (ema_trend.shift(self.p["slope_lookback"]) + 1e-9)

        vol_ma = v.rolling(self.p["vol_ma_len"]).mean()
        vol_surge = v > vol_ma * self.p["vol_surge_mult"]
        hbull, hbear, rbull, rbear = self.divergence(c, rsi)

        # 피벗 확인은 pivot_r봉 지연됨 → stoch 조건은 실제 피벗 시점에서 체크
        pr = self.p["pivot_r"]
        sf_pv = stoch_f.shift(pr)
        sm_pv = stoch_m.shift(pr)

        long_sig = (
            (hbull | rbull)
            & (sf_pv < self.p["stoch_oversold"])
            & (sf_pv > sm_pv)
            & (slope > self.p["slope_min"])
            & ((c > ema_trend) if self.p["use_ema_filter"] else True)
            & (rsi < self.p["rsi_max_entry"])
            & (vol_surge if self.p["use_vol_filter"] else True)
        )

        short_sig = (
            (hbear | rbear)
            & (sf_pv > self.p["stoch_overbought"])
            & (sf_pv < sm_pv)
            & (slope < -self.p["slope_min"])
            & ((c < ema_trend) if self.p["use_ema_filter"] else True)
            & (rsi > self.p["rsi_min_entry"])
            & (vol_surge if self.p["use_vol_filter"] else True)
        )

        signal = pd.Series(0, index=df.index, dtype=int)

        for i in range(len(df)):
            if i < self.p["warmup_bars"]:
                continue

            price = c.iloc[i]
            vol = atr.iloc[i]

            if self.long.active:
                if self.long.tp_price and price >= self.long.tp_price:
                    self.long.active = False
                    self.long.tp_price = None
                else:
                    trail_stop = self.long.extreme - vol * self.p["long_trail_mult"]
                    if price <= trail_stop:
                        self.long.active = False
                    if price > self.long.extreme:
                        self.long.extreme = price
                        if self.p["use_profit_lock"]:
                            profit_pct = (price - self.long.entry_price) / self.long.entry_price
                            if profit_pct > self.p["profit_lock_thresh"]:
                                self.long.tp_price = price + vol * self.p["tp_atr_mult"]

            if self.short.active:
                if self.short.tp_price and price <= self.short.tp_price:
                    self.short.active = False
                    self.short.tp_price = None
                else:
                    trail_stop = self.short.extreme + vol * self.p["short_trail_mult"]
                    if price >= trail_stop:
                        self.short.active = False
                    if price < self.short.extreme:
                        self.short.extreme = price
                        if self.p["use_profit_lock"]:
                            profit_pct = (self.short.entry_price - price) / self.short.entry_price
                            if profit_pct > self.p["profit_lock_thresh"]:
                                self.short.tp_price = price - vol * self.p["tp_atr_mult"]

            if long_sig.iloc[i] and not self.long.active:
                self.long.active = True
                self.long.entry_price = price
                self.long.extreme = price
                self.long.tp_price = None

            if short_sig.iloc[i] and not self.short.active:
                self.short.active = True
                self.short.entry_price = price
                self.short.extreme = price
                self.short.tp_price = None

            signal.iloc[i] = (1 if self.long.active else 0) + (-1 if self.short.active else 0)

        return signal.fillna(0).astype(int)


def _prepare_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    x.columns = [str(c).lower() for c in x.columns]

    required = ["open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in x.columns]
    if missing:
        return pd.DataFrame(columns=required)

    x = x.sort_index()
    x = x[~x.index.duplicated(keep="last")]

    for c in required:
        x[c] = pd.to_numeric(x[c], errors="coerce")

    x = x.dropna(subset=required)
    return x


def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:
    # Backtester contract: return index must match test_df.index.
    original_index = test_df.index
    df = _prepare_ohlcv(test_df)

    if len(df) < 20:
        return pd.Series(0, index=original_index, dtype=int)

    engine = RobustSignalEngineV2(BEST_PARAMS)
    signal = engine.run(df)

    return signal.reindex(original_index).fillna(0).astype(int)
