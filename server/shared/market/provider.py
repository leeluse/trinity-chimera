from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError
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
_BYBIT_KLINE_URL = "https://api.bybit.com/v5/market/kline"
_BYBIT_MAX_BARS_PER_REQ = 1000
_BYBIT_INTERVAL_MAP = {"1m": "1", "5m": "5", "15m": "15", "1h": "60", "4h": "240"}

# ── OHLCV 캐시 (5분 TTL) ────────────────────────────────────────────────────
# 최적화 파이프라인 등 동일 조건으로 반복 호출 시 실제 네트워크 요청을 1번으로 줄임
_OHLCV_CACHE: Dict[Tuple, Tuple[float, pd.DataFrame]] = {}
_CACHE_TTL = 300  # seconds


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


def _fetch_bybit_klines(
    symbol: str,
    interval: str,
    limit: int,
    start_ms: Optional[int] = None,
    end_ms: Optional[int] = None,
) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {
        "category": "linear",
        "symbol": sanitize_symbol(symbol),
        "interval": _BYBIT_INTERVAL_MAP[interval],
        "limit": max(1, min(int(limit), _BYBIT_MAX_BARS_PER_REQ)),
    }
    if start_ms is not None:
        params["start"] = int(start_ms)
    if end_ms is not None:
        params["end"] = int(end_ms)

    url = f"{_BYBIT_KLINE_URL}?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": "trinity-market-data/1.0"})

    for attempt in range(3):
        try:
            with urlopen(req, timeout=20) as resp:
                response_payload = json.loads(resp.read().decode("utf-8"))
            break
        except HTTPError as e:
            if e.code == 429:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(
                    "Bybit 요청 횟수 초과(429). 잠시 후 다시 시도해 주세요."
                ) from e
            raise
    else:
        raise RuntimeError("Bybit 데이터 수집 재시도 초과")

    if not isinstance(response_payload, dict):
        raise RuntimeError("Unexpected Bybit response")
    if int(response_payload.get("retCode", -1)) != 0:
        raise RuntimeError(f"Bybit error: {response_payload.get('retMsg', 'unknown error')}")

    result = response_payload.get("result") or {}
    rows = result.get("list") or []
    if not isinstance(rows, list):
        raise RuntimeError("Unexpected Bybit kline list format")

    out: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, list) or len(row) < 6:
            continue
        out.append(
            {
                "t": int(row[0]),
                "o": float(row[1]),
                "h": float(row[2]),
                "l": float(row[3]),
                "c": float(row[4]),
                "v": float(row[5]),
            }
        )
    return out


def fetch_ohlcv_dataframe(
    symbol: str,
    interval: str,
    limit: int = 1200,
    start_ms: Optional[int] = None,
    end_ms: Optional[int] = None,
) -> pd.DataFrame:
    if interval not in _ALLOWED_INTERVALS:
        raise ValueError(f"Invalid interval: {interval}")

    # 캐시 히트 확인 (최적화 루프 등 반복 호출 시 중복 요청 방지)
    cache_key = (sanitize_symbol(symbol), interval, limit, start_ms, end_ms)
    cached = _OHLCV_CACHE.get(cache_key)
    if cached is not None:
        ts, df = cached
        if time.time() - ts < _CACHE_TTL:
            return df.copy()
        del _OHLCV_CACHE[cache_key]

    rows: List[Dict[str, Any]] = []
    step = _INTERVAL_MS[interval]

    if start_ms is not None and end_ms is not None:
        current = int(start_ms)
        # 날짜 범위 지정 시에는 limit(호출자 기본값)에 의해 데이터가 잘리지 않도록
        # 요청 구간에 필요한 봉 개수를 자동 계산해 상한을 설정한다.
        estimated_bars = max(1, int((int(end_ms) - int(start_ms)) / step) + 2)
        max_bars = max(limit, estimated_bars, _BYBIT_MAX_BARS_PER_REQ)

        while current <= end_ms and len(rows) < max_bars:
            bars_remaining = max_bars - len(rows)
            request_bars = max(1, min(_BYBIT_MAX_BARS_PER_REQ, bars_remaining))
            window_end = min(end_ms, current + request_bars * step - 1)

            chunk = _fetch_bybit_klines(
                symbol=symbol,
                interval=interval,
                limit=request_bars,
                start_ms=current,
                end_ms=window_end,
            )
            if not chunk:
                current = window_end + 1
                continue
            rows.extend(chunk)

            last_open = max(int(item.get("t", 0)) for item in chunk)
            next_cursor = last_open + step
            if next_cursor <= current:
                break
            current = next_cursor

    else:
        bars = max(1, min(int(limit), 100_000))
        rows_acc: List[Dict[str, Any]] = []
        cursor_end = int(time.time() * 1000)
        while len(rows_acc) < bars:
            request_bars = min(_BYBIT_MAX_BARS_PER_REQ, bars - len(rows_acc))
            chunk = _fetch_bybit_klines(
                symbol=symbol,
                interval=interval,
                limit=request_bars,
                end_ms=cursor_end,
            )
            if not chunk:
                break
            rows_acc.extend(chunk)
            min_ts = min(int(item.get("t", 0)) for item in chunk)
            next_end = min_ts - step
            if next_end >= cursor_end:
                break
            cursor_end = next_end
            if len(chunk) < request_bars:
                break
        rows = rows_acc[-bars:]

    if not rows:
        return pd.DataFrame()

    frame = pd.DataFrame(
        [
            {
                "timestamp": datetime.fromtimestamp(int(r["t"]) / 1000, tz=timezone.utc),
                "open": float(r["o"]),
                "high": float(r["h"]),
                "low": float(r["l"]),
                "close": float(r["c"]),
                "volume": float(r.get("v", 0.0)),
            }
            for r in rows
            if "t" in r and "o" in r and "h" in r and "l" in r and "c" in r
        ]
    )

    frame = frame.sort_values("timestamp").drop_duplicates(subset=["timestamp"]).reset_index(drop=True)

    # 캐시 저장 (오래된 항목 정리 후 저장)
    if len(_OHLCV_CACHE) > 50:
        cutoff = time.time() - _CACHE_TTL
        stale = [k for k, (ts, _) in _OHLCV_CACHE.items() if ts < cutoff]
        for k in stale:
            del _OHLCV_CACHE[k]
    _OHLCV_CACHE[cache_key] = (time.time(), frame)

    return frame


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
