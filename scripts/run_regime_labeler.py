#!/usr/bin/env python3
"""
CLI runner for the regime labeler.

Usage:
    python scripts/run_regime_labeler.py [options]

Examples:
    # Default: BTCUSDT 1h from 2021-01-01 to 2026-01-31
    python scripts/run_regime_labeler.py

    # Custom range
    python scripts/run_regime_labeler.py --timeframe 15m --start 2022-01-01 --end 2024-12-31
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.modules.regime.labeler import run_regime_labeler


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate regime_labels.parquet via the regime labeler"
    )
    parser.add_argument("--symbol", default="BTCUSDT", help="Trading pair symbol (default: BTCUSDT)")
    parser.add_argument(
        "--timeframe",
        default="1h",
        choices=["15m", "1h"],
        help="Candle timeframe to use (default: 1h)",
    )
    parser.add_argument("--start", default="2021-01-01", help="Start date YYYY-MM-DD (default: 2021-01-01)")
    parser.add_argument("--end", default="2026-01-31", help="End date YYYY-MM-DD (default: 2026-01-31)")
    parser.add_argument(
        "--out-dir",
        default="",
        help="Output directory relative to project root (default: tmp/regime_runs)",
    )
    args = parser.parse_args()

    print(f"[labeler] symbol={args.symbol}  timeframe={args.timeframe}  {args.start} → {args.end}")
    print("[labeler] fetching market data and computing regime labels...")

    result = run_regime_labeler(
        symbol=args.symbol,
        timeframe=args.timeframe,
        start_date=args.start,
        end_date=args.end,
        out_dir=args.out_dir or None,
    )

    print()
    for log in result.get("logs", []):
        print(log)

    paths = result.get("artifact_paths", {})
    print()
    print("✅ Regime labeling complete!")
    print(f"   run_id  : {result['run_id']}")
    print(f"   parquet : {paths.get('parquet', '?')}")
    print(f"   stats   : {paths.get('stats', '?')}")
    print(f"   chart   : {paths.get('chart', '?')}")
    print()
    print("[tip] You can now run:")
    print("      python scripts/llm_refactor_regime_loop.py")
    print("      python scripts/regime_performance_analysis.py")


if __name__ == "__main__":
    main()
