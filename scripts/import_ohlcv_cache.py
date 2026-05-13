from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.shared.market.provider import fetch_ohlcv_dataframe, parse_date_to_ms, sanitize_symbol


def main() -> int:
    parser = argparse.ArgumentParser(description="Bulk import OHLCV candles into Supabase cache.")
    parser.add_argument("--symbols", nargs="+", default=["BTCUSDT"], help="Symbols to import, e.g. BTCUSDT ETHUSDT")
    parser.add_argument("--timeframes", nargs="+", default=["15m", "1h", "4h"], help="Timeframes to import")
    parser.add_argument("--start-date", default="2021-01-01", help="Inclusive UTC start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", default="2026-12-31", help="Inclusive UTC end date (YYYY-MM-DD)")
    args = parser.parse_args()

    start_ms = parse_date_to_ms(args.start_date, end_of_day=False)
    end_ms = parse_date_to_ms(args.end_date, end_of_day=True)

    if start_ms is None or end_ms is None:
        raise ValueError("start-date and end-date are required")

    for symbol in args.symbols:
        normalized_symbol = sanitize_symbol(symbol)
        for timeframe in args.timeframes:
            print(f"[import] {normalized_symbol} {timeframe} {args.start_date} -> {args.end_date}")
            frame = fetch_ohlcv_dataframe(
                symbol=normalized_symbol,
                interval=timeframe,
                limit=1_000_000,
                start_ms=start_ms,
                end_ms=end_ms,
            )
            print(f"[done] {normalized_symbol} {timeframe}: {len(frame)} rows")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
