from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

_ALLOWED_INTERVALS = {"1m", "5m", "15m", "1h", "4h"}
_INTERVAL_MS = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
}
_BINANCE_URL = "https://fapi.binance.com/fapi/v1/klines"


def sanitize_symbol(symbol: str) -> str:
    s = str(symbol or "").upper().replace("/", "").replace(" ", "")
    if not s.endswith("USDT"):
        s = f"{s}USDT"
    return s


def parse_date_to_ms(value: Optional[str], end_of_day: bool) -> Optional[int]:
    if not value:
        return None
    dt = datetime.strptime(value, "%Y-%m-%d")
    if end_of_day:
        dt = dt + timedelta(hours=23, minutes=59, seconds=59)
    dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _fetch_klines_chunk(
    symbol: str,
    interval: str,
    limit: int,
    start_ms: Optional[int] = None,
    end_ms: Optional[int] = None,
) -> List[List[Any]]:
    params: Dict[str, Any] = {
        "symbol": sanitize_symbol(symbol),
        "interval": interval,
        "limit": max(1, min(int(limit), 1500)),
    }
    if start_ms is not None:
        params["startTime"] = int(start_ms)
    if end_ms is not None:
        params["endTime"] = int(end_ms)

    url = f"{_BINANCE_URL}?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": "trinity-market-data/1.0"})
    with urlopen(req, timeout=20) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    if not isinstance(payload, list):
        raise RuntimeError("Unexpected Binance response")
    return payload


def fetch_ohlcv_dataframe(
    symbol: str,
    interval: str,
    limit: int = 1200,
    start_ms: Optional[int] = None,
    end_ms: Optional[int] = None,
) -> pd.DataFrame:
    if interval not in _ALLOWED_INTERVALS:
        raise ValueError(f"Invalid interval: {interval}")

    rows: List[List[Any]] = []

    if start_ms is not None and end_ms is not None:
        current = int(start_ms)
        max_bars = max(limit, 500)
        step = _INTERVAL_MS[interval]

        while current <= end_ms and len(rows) < max_bars:
            chunk = _fetch_klines_chunk(
                symbol=symbol,
                interval=interval,
                limit=min(1000, max_bars - len(rows)),
                start_ms=current,
                end_ms=end_ms,
            )
            if not chunk:
                break
            rows.extend(chunk)

            last_open = int(chunk[-1][0])
            next_cursor = last_open + step
            if next_cursor <= current:
                break
            current = next_cursor

            if len(chunk) < 1000:
                break
    else:
        rows = _fetch_klines_chunk(symbol=symbol, interval=interval, limit=limit)

    if not rows:
        return pd.DataFrame()

    frame = pd.DataFrame(
        [
            {
                "timestamp": datetime.fromtimestamp(int(r[0]) / 1000, tz=timezone.utc),
                "open": float(r[1]),
                "high": float(r[2]),
                "low": float(r[3]),
                "close": float(r[4]),
                "volume": float(r[5]),
            }
            for r in rows
        ]
    )

    return frame.sort_values("timestamp").drop_duplicates(subset=["timestamp"]).reset_index(drop=True)


def fetch_market_ohlcv(symbol: str, timeframe: str, limit: int = 240) -> Dict[str, Any]:
    frame = fetch_ohlcv_dataframe(symbol=symbol, interval=timeframe, limit=max(50, min(limit, 1500)))
    if frame.empty:
        return {"success": False, "error": "No OHLCV data", "candles": []}

    candles = [
        {
            "timestamp": row.timestamp.isoformat(),
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": float(row.volume),
        }
        for row in frame.itertuples(index=False)
    ]
    return {"success": True, "candles": candles}
