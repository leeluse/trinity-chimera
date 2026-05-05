#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

import sys
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.modules.backtest.backtest_engine import RealisticSimulator


def load_market_df(cache_path: Path) -> pd.DataFrame:
    df = pd.read_parquet(cache_path)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp")
    else:
        df.index = pd.to_datetime(df.index, utc=True)
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    df.columns = [str(c).lower() for c in df.columns]

    required = ["open", "high", "low", "close", "volume"]
    for col in required:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=required)


def load_regime_series(regime_labels_path: Path, market_index: pd.Index) -> pd.Series:
    df = pd.read_parquet(regime_labels_path)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp")
    else:
        df.index = pd.to_datetime(df.index, utc=True)
    df = df.sort_index()
    if "regime" not in df.columns:
        raise RuntimeError("regime_labels.parquet missing 'regime' column")
    return df["regime"].reindex(market_index).ffill().bfill().fillna("Range")


def extract_segments(
    df: pd.DataFrame,
    regime_series: pd.Series,
    target_regime: str = "Bear",
    min_bars: int = 500,
    max_gap_bars: int = 20,
) -> List[pd.DataFrame]:
    mask = (regime_series.reindex(df.index).ffill().fillna("Range") == target_regime)

    blocks: List[Tuple[int, int]] = []
    in_block = False
    start_idx = 0
    for i in range(len(df)):
        if mask.iloc[i] and not in_block:
            in_block = True
            start_idx = i
        elif not mask.iloc[i] and in_block:
            in_block = False
            blocks.append((start_idx, i))
    if in_block:
        blocks.append((start_idx, len(df)))

    if not blocks:
        return []

    merged: List[Tuple[int, int]] = [blocks[0]]
    for s, e in blocks[1:]:
        ps, pe = merged[-1]
        gap = s - pe
        if gap <= max_gap_bars:
            merged[-1] = (ps, e)
        else:
            merged.append((s, e))

    segments: List[pd.DataFrame] = []
    for s, e in merged:
        seg = df.iloc[s:e]
        if len(seg) >= min_bars:
            segments.append(seg)
    return segments


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(c: pd.Series, n: int = 14) -> pd.Series:
    d = c.diff()
    up = d.where(d > 0, 0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.where(d < 0, 0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / (dn + 1e-9)
    return 100 - (100 / (1 + rs))


def atr(h: pd.Series, l: pd.Series, c: pd.Series, n: int = 14) -> pd.Series:
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(span=n, adjust=False).mean()


def build_signal(ctx: pd.DataFrame, p: Dict[str, float]) -> pd.Series:
    c = ctx["close"]
    h = ctx["high"]
    l = ctx["low"]
    v = ctx["volume"]

    ef = ema(c, int(p["ema_fast"]))
    es = ema(c, int(p["ema_slow"]))
    et = ema(c, int(p["ema_trend"]))
    r = rsi(c, int(p["rsi_len"]))
    a = atr(h, l, c, int(p["atr_len"]))
    vm = v.rolling(int(p["vol_len"])).mean()

    down = (ef < es) & (es < et)
    slope = (et - et.shift(int(p["slope_lb"]))) / (et.shift(int(p["slope_lb"])) + 1e-9)
    pull = (c > ef) & (c < es + a * float(p["pullback_atr"]))
    breakdown = c < l.shift(1)
    rsi_ok = (r > float(p["rsi_min"])) & (r < float(p["rsi_max"]))
    vol_ok = v > vm * float(p["vol_mult"])

    enter = (
        down.shift(1).fillna(False)
        & (slope.shift(1) < -float(p["slope_min"]))
        & pull.shift(1).fillna(False)
        & breakdown
        & rsi_ok
        & vol_ok
    )

    sig = pd.Series(0, index=ctx.index, dtype=int)
    in_pos = False
    stop = 0.0
    tp = 0.0
    cooldown = 0
    hold_bars = 0
    warmup = max(int(p["warmup"]), int(p["ema_trend"]) + 5)

    for i in range(len(ctx)):
        if i < warmup:
            continue

        if cooldown > 0:
            cooldown -= 1

        price = float(c.iloc[i]) if not np.isnan(c.iloc[i]) else np.nan
        lo = float(l.iloc[i]) if not np.isnan(l.iloc[i]) else np.nan
        hi = float(h.iloc[i]) if not np.isnan(h.iloc[i]) else np.nan
        atr_now = float(a.iloc[i]) if not np.isnan(a.iloc[i]) else np.nan

        if np.isnan(price) or np.isnan(atr_now) or atr_now <= 0:
            sig.iloc[i] = -1 if in_pos else 0
            continue

        if in_pos:
            hold_bars += 1
            stop = min(stop, price + atr_now * float(p["trail_atr"]))
            exit_now = (
                (hi >= stop)
                or (lo <= tp)
                or (r.iloc[i] < float(p["take_rsi"]))
                or (price > es.iloc[i] + atr_now * float(p["exit_atr"]))
                or (hold_bars >= int(p["max_hold_bars"]))
            )
            if exit_now:
                in_pos = False
                cooldown = int(p["cooldown"])
                hold_bars = 0
                sig.iloc[i] = 0
            else:
                sig.iloc[i] = -1
        else:
            if cooldown == 0 and bool(enter.iloc[i]):
                in_pos = True
                hold_bars = 0
                stop = price + atr_now * float(p["sl_atr"])
                tp = price - atr_now * float(p["tp_atr"])
                sig.iloc[i] = -1
            else:
                sig.iloc[i] = 0
    return sig


def evaluate_params(
    segments: List[pd.DataFrame],
    params: Dict[str, float],
    oos_ratio: float,
    min_test_bars: int,
) -> Dict[str, float]:
    sim = RealisticSimulator(max_position=1.0, freq=96)
    returns_parts: List[pd.Series] = []
    trades_all: List[float] = []

    for seg in segments:
        split = max(1, int(len(seg) * (1.0 - oos_ratio)))
        train_seg = seg.iloc[:split]
        test_seg = seg.iloc[split:]
        if len(test_seg) < min_test_bars:
            continue

        ctx = pd.concat([train_seg.tail(320), test_seg])
        sig_ctx = build_signal(ctx, params)
        sig = sig_ctx.iloc[len(train_seg.tail(320)) :]
        seg_returns, _, seg_trades, _, _, _ = sim.run(test_seg, sig)
        returns_parts.append(seg_returns)
        trades_all.extend(seg_trades)

    if not returns_parts:
        return {}

    returns = pd.concat(returns_parts).sort_index()
    total_return = float((1.0 + returns).prod() - 1.0)
    pos_sum = float(returns[returns > 0].sum())
    neg_sum = float(returns[returns < 0].sum())
    pf = pos_sum / abs(neg_sum) if neg_sum < 0 else (pos_sum if pos_sum > 0 else 0.0)
    eq = (1.0 + returns).cumprod()
    mdd = float((eq / eq.cummax() - 1.0).min()) if len(eq) else 0.0
    sharpe = float(returns.mean() / (returns.std() + 1e-12) * np.sqrt(365 * 96)) if len(returns) else 0.0
    trades = int(len(trades_all))

    return {
        "profit_factor": float(pf),
        "total_return": total_return,
        "max_drawdown": mdd,
        "sharpe": sharpe,
        "trades": trades,
    }


def score_metrics(metrics: Dict[str, float], min_trades: int) -> float:
    pf = float(metrics.get("profit_factor", 0.0))
    total = float(metrics.get("total_return", 0.0))
    mdd = float(metrics.get("max_drawdown", 0.0))
    sharpe = float(metrics.get("sharpe", 0.0))
    trades = int(metrics.get("trades", 0))

    score = pf + total * 0.2 + sharpe * 0.05 + mdd * 0.25
    if trades < min_trades:
        score -= (min_trades - trades) * 0.06
    return float(score)


def random_params(space: Dict[str, List[float]]) -> Dict[str, float]:
    p = {k: random.choice(v) for k, v in space.items()}
    return p


def main() -> None:
    parser = argparse.ArgumentParser(description="Random-search optimizer for Bear_04 regime-sliced OOS")
    parser.add_argument("--ohlcv-cache", default="tmp/cache/ohlcv/BTCUSDT_15m_2021-01-01_2026-01-31.parquet")
    parser.add_argument("--regime-labels", default="tmp/regime_runs/20260428_163511_316609/regime_labels.parquet")
    parser.add_argument("--iterations", type=int, default=160)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-bars", type=int, default=500)
    parser.add_argument("--max-gap-bars", type=int, default=20)
    parser.add_argument("--oos-ratio", type=float, default=0.4)
    parser.add_argument("--min-trades", type=int, default=20)
    parser.add_argument("--out", default="tmp/regime/bear04_optimize_results.json")
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    market_df = load_market_df(PROJECT_ROOT / args.ohlcv_cache)
    regime_series = load_regime_series(PROJECT_ROOT / args.regime_labels, market_df.index)
    segments = extract_segments(
        market_df,
        regime_series,
        target_regime="Bear",
        min_bars=int(args.min_bars),
        max_gap_bars=int(args.max_gap_bars),
    )
    if not segments:
        raise RuntimeError("No Bear segments found for optimization.")

    search_space: Dict[str, List[float]] = {
        "ema_fast": [10, 12, 15, 20],
        "ema_slow": [25, 30, 35, 40, 50],
        "ema_trend": [120, 150, 180, 200],
        "rsi_len": [10, 12, 14],
        "atr_len": [10, 14],
        "vol_len": [20, 30],
        "slope_lb": [6, 8, 10, 12],
        "pullback_atr": [0.1, 0.2, 0.3, 0.4, 0.6],
        "slope_min": [0.0002, 0.0004, 0.0006],
        "rsi_min": [45, 48, 50],
        "rsi_max": [68, 72, 75],
        "vol_mult": [0.7, 0.8, 0.9, 1.0],
        "sl_atr": [1.0, 1.2, 1.3, 1.6, 1.8],
        "tp_atr": [1.8, 2.2, 2.6, 3.0],
        "trail_atr": [1.8, 2.2, 2.6],
        "take_rsi": [22, 24, 28, 32],
        "exit_atr": [0.4, 0.6, 0.8, 1.0],
        "cooldown": [0, 1, 2, 3],
        "max_hold_bars": [36, 48, 72, 96],
        "warmup": [120, 180, 240],
    }

    rows: List[Dict[str, object]] = []
    for i in range(int(args.iterations)):
        p = random_params(search_space)
        if not (p["ema_fast"] < p["ema_slow"] < p["ema_trend"]):
            continue
        if not (p["rsi_min"] < p["rsi_max"]):
            continue

        metrics = evaluate_params(
            segments=segments,
            params=p,
            oos_ratio=float(args.oos_ratio),
            min_test_bars=30,
        )
        if not metrics:
            continue

        score = score_metrics(metrics, min_trades=int(args.min_trades))
        rows.append(
            {
                "iter": i + 1,
                "score": score,
                "metrics": metrics,
                "params": p,
            }
        )

    rows.sort(key=lambda r: float(r["score"]), reverse=True)
    top = rows[:10]
    strong = [
        r for r in rows
        if int(r["metrics"]["trades"]) >= int(args.min_trades) and float(r["metrics"]["profit_factor"]) >= 1.0
    ]

    payload = {
        "meta": {
            "iterations": int(args.iterations),
            "seed": int(args.seed),
            "segments": int(len(segments)),
            "min_bars": int(args.min_bars),
            "max_gap_bars": int(args.max_gap_bars),
            "oos_ratio": float(args.oos_ratio),
            "min_trades": int(args.min_trades),
            "ohlcv_cache": args.ohlcv_cache,
            "regime_labels": args.regime_labels,
            "evaluated": int(len(rows)),
            "strong_count": int(len(strong)),
        },
        "best": rows[0] if rows else None,
        "top10": top,
        "strong_top10": strong[:10],
    }

    out_path = PROJECT_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[done] saved: {out_path}")
    print(f"[done] evaluated={len(rows)} strong={len(strong)} segments={len(segments)}")
    if rows:
        b = rows[0]
        print(
            "[best] score={:.4f} pf={:.3f} ret={:+.3%} mdd={:+.3%} trades={}".format(
                float(b["score"]),
                float(b["metrics"]["profit_factor"]),
                float(b["metrics"]["total_return"]),
                float(b["metrics"]["max_drawdown"]),
                int(b["metrics"]["trades"]),
            )
        )
    if strong:
        s = strong[0]
        print(
            "[strong-best] score={:.4f} pf={:.3f} ret={:+.3%} mdd={:+.3%} trades={}".format(
                float(s["score"]),
                float(s["metrics"]["profit_factor"]),
                float(s["metrics"]["total_return"]),
                float(s["metrics"]["max_drawdown"]),
                int(s["metrics"]["trades"]),
            )
        )


if __name__ == "__main__":
    main()

