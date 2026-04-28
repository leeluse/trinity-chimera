#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

import sys
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.modules.backtest.backtest_engine import RealisticSimulator
from server.shared.market.provider import fetch_ohlcv_dataframe, parse_date_to_ms

TF_BARS_PER_DAY = {
    "1m": 1440,
    "5m": 288,
    "15m": 96,
    "1h": 24,
    "4h": 6,
}

REGIME_ORDER = ["Bull", "Bear", "Range", "HighVol"]


@dataclass
class Trade:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    direction: int
    pnl: float
    hold_bars: int


def _load_module_from_file(file_path: Path):
    module_name = f"regime_perf_{file_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module from {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _discover_strategy_files(strategies_dir: Path) -> List[Path]:
    files = []
    for p in sorted(strategies_dir.glob("*.py")):
        if p.name.startswith("_"):
            continue
        files.append(p)
    return files


def _find_latest_regime_labels() -> Optional[Path]:
    root = PROJECT_ROOT / "tmp" / "regime_runs"
    if not root.exists():
        return None
    candidates = list(root.glob("*/regime_labels.parquet"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _load_market_df(
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    start_ms = parse_date_to_ms(start_date, end_of_day=False)
    end_ms = parse_date_to_ms(end_date, end_of_day=True)
    if start_ms is None or end_ms is None or end_ms <= start_ms:
        raise ValueError("Invalid date range")

    interval_ms = {
        "1m": 60_000,
        "5m": 300_000,
        "15m": 900_000,
        "1h": 3_600_000,
        "4h": 14_400_000,
    }[timeframe]
    expected_bars = int((end_ms - start_ms) / interval_ms) + 2
    df = fetch_ohlcv_dataframe(
        symbol=symbol,
        interval=timeframe,
        limit=max(expected_bars, 10_000),
        start_ms=start_ms,
        end_ms=end_ms,
    )
    if df.empty:
        raise RuntimeError("No market data found")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df


def _compute_max_consecutive_losses(trade_pnls: List[float]) -> int:
    streak = 0
    best = 0
    for p in trade_pnls:
        if p < 0:
            streak += 1
            best = max(best, streak)
        else:
            streak = 0
    return best


def _extract_trades_from_returns(
    df: pd.DataFrame,
    signal: pd.Series,
    strategy_returns: pd.Series,
    leverage: float,
) -> List[Trade]:
    position = signal.shift(1).fillna(0).clip(-leverage, leverage)
    trades: List[Trade] = []
    in_trade = False
    entry_idx = 0
    direction = 0
    trade_curve = 1.0

    for i in range(1, len(df)):
        curr_pos = int(np.sign(position.iloc[i]))
        prev_pos = int(np.sign(position.iloc[i - 1]))

        if curr_pos != prev_pos:
            if in_trade:
                exit_idx = i - 1
                trades.append(
                    Trade(
                        entry_time=df.index[entry_idx],
                        exit_time=df.index[exit_idx],
                        direction=direction,
                        pnl=float(trade_curve - 1.0),
                        hold_bars=max(1, exit_idx - entry_idx + 1),
                    )
                )
                in_trade = False
                trade_curve = 1.0

            if curr_pos != 0:
                in_trade = True
                entry_idx = i
                direction = curr_pos

        if in_trade:
            trade_curve *= (1.0 + float(strategy_returns.iloc[i]))

    if in_trade:
        trades.append(
            Trade(
                entry_time=df.index[entry_idx],
                exit_time=df.index[-1],
                direction=direction,
                pnl=float(trade_curve - 1.0),
                hold_bars=max(1, len(df) - entry_idx),
            )
        )
    return trades


def _metrics_from_returns(
    returns: pd.Series,
    trade_pnls: List[float],
    hold_bars: List[int],
    exposure_ratio: float,
    bars_per_day: int,
) -> Dict[str, float]:
    if returns.empty:
        return {
            "total_return": 0.0,
            "monthly_return": 0.0,
            "profit_factor": 0.0,
            "mdd": 0.0,
            "sharpe": 0.0,
            "max_consecutive_losses": 0,
            "trades": 0,
            "exposure_ratio": exposure_ratio,
            "avg_hold_bars": 0.0,
            "avg_hold_hours": 0.0,
            "win_rate": 0.0,
        }

    total_return = float((1.0 + returns).prod() - 1.0)
    monthly_series = returns.groupby(pd.Grouper(freq="MS")).apply(lambda s: (1.0 + s).prod() - 1.0)
    monthly_series = monthly_series.dropna()
    monthly_return = float(monthly_series.mean()) if len(monthly_series) > 0 else 0.0

    pos_sum = float(returns[returns > 0].sum())
    neg_sum = float(returns[returns < 0].sum())
    profit_factor = pos_sum / abs(neg_sum) if neg_sum < 0 else (pos_sum if pos_sum > 0 else 0.0)

    eq = (1.0 + returns).cumprod()
    peak = eq.cummax()
    dd = (eq - peak) / peak
    mdd = float(dd.min()) if len(dd) else 0.0

    mu = float(returns.mean())
    sigma = float(returns.std()) + 1e-12
    sharpe = (mu / sigma) * np.sqrt(365 * bars_per_day) if sigma > 0 else 0.0

    wins = [p for p in trade_pnls if p > 0]
    win_rate = (len(wins) / len(trade_pnls)) if trade_pnls else 0.0
    max_loss_streak = _compute_max_consecutive_losses(trade_pnls)
    avg_hold = float(np.mean(hold_bars)) if hold_bars else 0.0

    return {
        "total_return": total_return,
        "monthly_return": monthly_return,
        "profit_factor": float(profit_factor),
        "mdd": mdd,
        "sharpe": float(sharpe),
        "max_consecutive_losses": int(max_loss_streak),
        "trades": int(len(trade_pnls)),
        "exposure_ratio": float(exposure_ratio),
        "avg_hold_bars": avg_hold,
        "avg_hold_hours": avg_hold * (24.0 / bars_per_day),
        "win_rate": float(win_rate),
    }


def _regime_diagnosis(per_regime: Dict[str, Dict[str, float]]) -> List[str]:
    notes: List[str] = []
    for regime in REGIME_ORDER:
        m = per_regime.get(regime, {})
        pf = float(m.get("profit_factor", 0.0))
        mdd = float(m.get("mdd", 0.0))
        if pf < 1.0 and mdd < -0.15:
            notes.append(f"✗ {regime} 구간 손실 주범 (PF {pf:.2f}, MDD {mdd:.1%})")
        elif pf < 1.0:
            notes.append(f"✗ {regime} 구간 수익성 약함 (PF {pf:.2f})")
        elif pf >= 1.5 and mdd > -0.1:
            notes.append(f"✓ {regime} 구간 안정적 (PF {pf:.2f}, MDD {mdd:.1%})")
    if not notes:
        notes.append("• 뚜렷한 강/약 구간이 약함. 추가 샘플 필요")
    return notes


def analyze_strategy_by_regime(
    strategy_name: str,
    strategy_fn,
    df: pd.DataFrame,
    regime_series: pd.Series,
    bars_per_day: int,
    leverage: float,
) -> Dict[str, Any]:
    train_df = df.iloc[: len(df) // 2]
    signal = strategy_fn(train_df, df)
    if not isinstance(signal, pd.Series):
        signal = pd.Series(signal, index=df.index)
    signal = pd.to_numeric(signal.reindex(df.index), errors="coerce").fillna(0.0)
    signal = pd.Series(np.sign(signal).astype(int), index=df.index)

    sim = RealisticSimulator(max_position=max(0.0, leverage), freq=bars_per_day)
    strategy_returns, _, _, _, _, _ = sim.run(df, signal)
    position = signal.shift(1).fillna(0).clip(-leverage, leverage)

    trades = _extract_trades_from_returns(df, signal, strategy_returns, leverage=leverage)
    trade_df = pd.DataFrame(
        [
            {
                "entry_time": t.entry_time,
                "exit_time": t.exit_time,
                "direction": t.direction,
                "pnl": t.pnl,
                "hold_bars": t.hold_bars,
            }
            for t in trades
        ]
    )

    if not trade_df.empty:
        entry_regimes = regime_series.reindex(pd.to_datetime(trade_df["entry_time"], utc=True)).values
        trade_df["entry_regime"] = entry_regimes

    overall_trade_pnls = trade_df["pnl"].tolist() if not trade_df.empty else []
    overall_holds = trade_df["hold_bars"].tolist() if not trade_df.empty else []
    overall_exposure = float((position != 0).mean())
    overall = _metrics_from_returns(
        strategy_returns,
        overall_trade_pnls,
        overall_holds,
        overall_exposure,
        bars_per_day=bars_per_day,
    )

    by_regime: Dict[str, Dict[str, float]] = {}
    for regime in REGIME_ORDER:
        mask = regime_series == regime
        reg_returns = strategy_returns[mask]
        reg_exposure = float((position[mask] != 0).mean()) if int(mask.sum()) > 0 else 0.0
        if not trade_df.empty:
            sub_trades = trade_df[trade_df["entry_regime"] == regime]
            trade_pnls = sub_trades["pnl"].tolist()
            hold_bars = sub_trades["hold_bars"].tolist()
        else:
            trade_pnls = []
            hold_bars = []
        by_regime[regime] = _metrics_from_returns(
            reg_returns,
            trade_pnls,
            hold_bars,
            reg_exposure,
            bars_per_day=bars_per_day,
        )

    return {
        "strategy": strategy_name,
        "overall": overall,
        "by_regime": by_regime,
        "diagnosis": _regime_diagnosis(by_regime),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage-2: Regime-specific strategy performance analysis")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--timeframe", default="15m")
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument("--end", default="2026-01-31")
    parser.add_argument("--leverage", type=float, default=1.0)
    parser.add_argument("--regime-labels", default="", help="Path to regime_labels.parquet (optional)")
    parser.add_argument("--strategies-dir", default="server/strategies")
    parser.add_argument("--out", default="tmp/regime/regime_performance.json")
    args = parser.parse_args()

    regime_path = Path(args.regime_labels) if args.regime_labels else _find_latest_regime_labels()
    if regime_path is None or not regime_path.exists():
        raise RuntimeError("regime_labels.parquet not found. Run regime labeler first.")

    df = _load_market_df(args.symbol, args.timeframe, args.start, args.end)

    regime_df = pd.read_parquet(regime_path)
    if "timestamp" in regime_df.columns:
        regime_df["timestamp"] = pd.to_datetime(regime_df["timestamp"], utc=True)
        regime_df = regime_df.set_index("timestamp")
    else:
        regime_df.index = pd.to_datetime(regime_df.index, utc=True)
    regime_df = regime_df.sort_index()
    if "regime" not in regime_df.columns:
        raise RuntimeError("regime_labels.parquet missing 'regime' column")

    regime_series = regime_df["regime"].reindex(df.index).ffill().bfill()
    regime_series = regime_series.fillna("Range")

    strategies_dir = PROJECT_ROOT / args.strategies_dir
    strategy_files = _discover_strategy_files(strategies_dir)
    if not strategy_files:
        raise RuntimeError(f"No strategy files found in {strategies_dir}")

    bars_per_day = TF_BARS_PER_DAY.get(args.timeframe, 96)

    reports = []
    failed = []
    for file_path in strategy_files:
        strategy_key = file_path.stem
        try:
            mod = _load_module_from_file(file_path)
            fn = getattr(mod, "generate_signal", None)
            if not callable(fn):
                failed.append({"strategy": strategy_key, "error": "generate_signal not found"})
                continue
            report = analyze_strategy_by_regime(
                strategy_name=strategy_key,
                strategy_fn=fn,
                df=df,
                regime_series=regime_series,
                bars_per_day=bars_per_day,
                leverage=float(args.leverage),
            )
            reports.append(report)
        except Exception as exc:
            failed.append({"strategy": strategy_key, "error": str(exc)})

    weakness = {r: 0 for r in REGIME_ORDER}
    for rep in reports:
        for r in REGIME_ORDER:
            m = rep["by_regime"].get(r, {})
            if float(m.get("profit_factor", 0.0)) < 1.0:
                weakness[r] += 1

    priority = sorted(weakness.items(), key=lambda kv: kv[1], reverse=True)
    out_payload = {
        "meta": {
            "symbol": args.symbol,
            "timeframe": args.timeframe,
            "start": args.start,
            "end": args.end,
            "bars": int(len(df)),
            "regime_labels_path": str(regime_path),
            "strategies_dir": str(strategies_dir),
            "strategy_count": len(strategy_files),
            "analyzed_count": len(reports),
            "failed_count": len(failed),
        },
        "strategies": reports,
        "weakness_map": weakness,
        "module_priority": [r for r, _ in priority],
        "failed": failed,
    }

    out_path = PROJECT_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[done] saved: {out_path}")
    print(f"[done] analyzed={len(reports)} failed={len(failed)}")
    print("[priority]", " > ".join(out_payload["module_priority"]))
    for r in REGIME_ORDER:
        print(f"  - {r}: weak in {weakness[r]}/{len(reports)} strategies")


if __name__ == "__main__":
    main()

