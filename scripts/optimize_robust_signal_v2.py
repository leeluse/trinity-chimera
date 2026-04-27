#!/usr/bin/env python3
"""
RobustSignalEngineV2 
"""
BEST_PARAMS = {
    "atr_len": 14,
    "rsi_len": 12,
    "rsi_ma_len": 3,
    "stoch_f_len": 3,
    "stoch_m_len": 14,
    "ema_trend": 150,
    "ema_fast": 20,
    "slope_lookback": 10,
    "stoch_oversold": 30,
    "stoch_overbought": 85,
    "slope_min": 0.1,
    "rsi_max_entry": 50,
    "rsi_min_entry": 50,
    "long_trail_mult": 2.0,
    "short_trail_mult": 3.0,
    "tp_atr_mult": 1.5,
    "profit_lock_thresh": 0.02,
    "pivot_l": 7,
    "pivot_r": 7,
    "vol_ma_len": 20,
    "vol_surge_mult": 1.2,
    "use_ema_filter": False,
    "use_vol_filter": False,
    "use_profit_lock": True,
    "warmup_bars": 150,
}
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

# Ensure project root is importable when running as a script.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.shared.market.provider import (
    fetch_ohlcv_dataframe,
    parse_date_to_ms,
)


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
    def pivot_low(s: pd.Series, left: int = 5, right: int = 5) -> pd.Series:
        return (s.shift(left) > s) & (s.shift(-right) > s)

    @staticmethod
    def pivot_high(s: pd.Series, left: int = 5, right: int = 5) -> pd.Series:
        return (s.shift(left) < s) & (s.shift(-right) < s)

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
        slope = ema_trend - ema_trend.shift(self.p["slope_lookback"])

        vol_ma = v.rolling(self.p["vol_ma_len"]).mean()
        vol_surge = v > vol_ma * self.p["vol_surge_mult"]
        hbull, hbear, rbull, rbear = self.divergence(c, rsi)

        long_sig = (
            (hbull | rbull)
            & (stoch_f < self.p["stoch_oversold"])
            & (stoch_f > stoch_m)
            & (slope > self.p["slope_min"])
            & ((c > ema_trend) if self.p["use_ema_filter"] else True)
            & (rsi < self.p["rsi_max_entry"])
            & (vol_surge if self.p["use_vol_filter"] else True)
        )

        short_sig = (
            (hbear | rbear)
            & (stoch_f > self.p["stoch_overbought"])
            & (stoch_f < stoch_m)
            & (slope < -self.p["slope_min"])
            & ((c < ema_trend) if self.p["use_ema_filter"] else True)
            & (rsi > self.p["rsi_min_entry"])
            & (vol_surge if self.p["use_vol_filter"] else True)
        )

        signal = pd.Series(0, index=df.index)

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

        return signal.fillna(0)


def _annualization_factor(timeframe: str) -> float:
    bars_per_day = {
        "1m": 24 * 60,
        "5m": 24 * 12,
        "15m": 24 * 4,
        "1h": 24,
        "4h": 6,
    }.get(timeframe, 24)
    return float(np.sqrt(365 * bars_per_day))


def main() -> None:
    parser = argparse.ArgumentParser(description="Random search optimizer for RobustSignalEngineV2")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--timeframe", default="1h", choices=["1m", "5m", "15m", "1h", "4h"])
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument("--end", default="2026-04-28")
    parser.add_argument("--iters", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--topk", type=int, default=10)
    parser.add_argument("--progress", type=int, default=100)
    parser.add_argument("--out", default="tmp/robust_v2_best_params.json")
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    start_ms = parse_date_to_ms(args.start, end_of_day=False)
    end_ms = parse_date_to_ms(args.end, end_of_day=True)
    if start_ms is None or end_ms is None or end_ms <= start_ms:
        raise ValueError("Invalid --start/--end date range. Use YYYY-MM-DD with start < end.")

    interval_ms = {"1m": 60_000, "5m": 300_000, "15m": 900_000, "1h": 3_600_000, "4h": 14_400_000}[args.timeframe]
    expected_bars = int((end_ms - start_ms) / interval_ms) + 2

    df = fetch_ohlcv_dataframe(
        symbol=args.symbol,
        interval=args.timeframe,
        limit=max(10_000, expected_bars),
        start_ms=start_ms,
        end_ms=end_ms,
    )
    if df.empty:
        raise RuntimeError("No market data loaded for the requested range.")

    annualization = _annualization_factor(args.timeframe)
    keys = list(PARAM_GRID.keys())
    results: List[Dict[str, Any]] = []

    print(f"Loaded {len(df)} candles for {args.symbol} {args.timeframe} ({args.start} ~ {args.end})")
    print(f"Starting random search: {args.iters} iterations")

    for i in range(args.iters):
        params = {k: random.choice(PARAM_GRID[k]) for k in keys}
        try:
            metrics = run_backtest(params, df, annualization_factor=annualization)
            metrics["params"] = params
            results.append(metrics)
        except Exception:
            continue

        if (i + 1) % max(1, args.progress) == 0 and results:
            best_sharpe = max(item["sharpe"] for item in results)
            print(f"Progress: {i + 1}/{args.iters} | Best Sharpe: {best_sharpe:.3f}")

    if not results:
        raise RuntimeError("All iterations failed.")

    results_df = pd.DataFrame(results).sort_values("sharpe", ascending=False).reset_index(drop=True)
    print("\nTOP RESULTS")
    for rank, row in results_df.head(args.topk).iterrows():
        print(
            f"#{rank + 1} Sharpe={row['sharpe']:.3f} Return={row['total_return']:.2%} "
            f"WinRate={row['win_rate']:.1%} Trades={int(row['trades'])} PF={row['profit_factor']:.2f}"
        )

    best = results_df.iloc[0].to_dict()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "symbol": args.symbol,
                "timeframe": args.timeframe,
                "start": args.start,
                "end": args.end,
                "iters": args.iters,
                "best": {
                    "sharpe": float(best["sharpe"]),
                    "total_return": float(best["total_return"]),
                    "win_rate": float(best["win_rate"]),
                    "max_dd": float(best["max_dd"]),
                    "trades": int(best["trades"]),
                    "profit_factor": float(best["profit_factor"]),
                    "params": best["params"],
                },
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"\nBest params saved: {out_path}")
def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:
    df = test_df.copy()
    df.columns = [str(c).lower() for c in df.columns]
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    req = ["open", "high", "low", "close", "volume"]
    for c in req:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=req)

    if len(df) < 20:
        return pd.Series(0, index=test_df.index, dtype=int)

    engine = RobustSignalEngineV2(BEST_PARAMS)
    sig = engine.run(df).fillna(0).clip(-1, 1).astype(int)

    # 백테스터 인덱스 규격 맞춤 + asc 정렬 이슈 방지
    return sig.reindex(test_df.index).fillna(0).astype(int)

if __name__ == "__main__":
    main()
