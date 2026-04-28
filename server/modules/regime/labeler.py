from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

from server.shared.market.provider import fetch_ohlcv_dataframe, parse_date_to_ms

PROJECT_ROOT = Path(__file__).resolve().parents[3]

REGIME_PARAMS = {
    "trend_ema_period": 20,
    "trend_lookback": 80,
    "bull_threshold": 0.25,
    "bear_threshold": -0.25,
    "range_slope_abs_max": 0.35,
    "range_efficiency_max": 0.45,
    "range_atr_ratio_max": 0.85,
    "atr_period": 56,
    "highvol_atr_threshold": 0.65,
    "highvol_price_change_1h": 1.2,
    "highvol_extreme": 1.25,
    "highvol_extreme_price_change_1h": 4.0,
    "min_regime_bars": 48,
    "highvol_max_bars": 192,
    "range_entry_confirm_bars": 12,
    "trend_entry_confirm_bars": 6,
    "highvol_entry_confirm_bars": 4,
}

REGIME_COLORS = {
    "Bull": "#26a69a",
    "Bear": "#ef5350",
    "Range": "#b0bec5",
    "HighVol": "#ff9800",
}

ARTIFACT_MAP = {
    "parquet": "regime_labels.parquet",
    "stats": "regime_stats.json",
    "chart": "regime_chart.html",
}
DEFAULT_VALIDATION_START = "2021-01-01"
DEFAULT_VALIDATION_END = "2026-01-31"


def compute_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def compute_atr(df: pd.DataFrame, period: int) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    p = REGIME_PARAMS
    out = df.copy()
    out["ema"] = compute_ema(out["close"], p["trend_ema_period"])
    out["ema_slope"] = (
        (out["ema"] - out["ema"].shift(p["trend_lookback"]))
        / out["ema"].shift(p["trend_lookback"])
        * 100
    )
    out["atr"] = compute_atr(out, p["atr_period"])
    out["atr_ratio"] = out["atr"] / out["close"] * 100
    # 15m 기준 4봉=1시간 가격변화율(%)
    out["price_change_1h"] = out["close"].pct_change(4) * 100
    # 경로 효율성: 낮을수록 횡보(잡음), 높을수록 방향성 추세
    path_20 = out["close"].diff().abs().rolling(20).sum()
    out["efficiency_20"] = (out["close"] - out["close"].shift(20)).abs() / (path_20 + 1e-9)
    return out


def label_raw(df: pd.DataFrame) -> pd.Series:
    p = REGIME_PARAMS
    labels = label_base(df)
    highvol_mask = (
        (df["atr_ratio"] > p["highvol_atr_threshold"])
        & (df["price_change_1h"].abs() > p["highvol_price_change_1h"])
    )
    labels[highvol_mask] = "HighVol"
    return labels


def label_base(df: pd.DataFrame) -> pd.Series:
    p = REGIME_PARAMS
    labels = pd.Series("Range", index=df.index, dtype=object)
    labels[df["ema_slope"] < p["bear_threshold"]] = "Bear"
    labels[df["ema_slope"] > p["bull_threshold"]] = "Bull"
    range_cond = (
        (df["ema_slope"].abs() <= p["range_slope_abs_max"])
        & (df["efficiency_20"] <= p["range_efficiency_max"])
        & (df["atr_ratio"] <= p["range_atr_ratio_max"])
    )
    labels[range_cond] = "Range"
    return labels


def apply_hysteresis(labels: pd.Series) -> pd.Series:
    p = REGIME_PARAMS
    if labels.empty:
        return labels.copy()

    out = labels.copy()
    current = str(labels.iloc[0])
    pending = None
    pending_count = 0
    out.iloc[0] = current

    for i in range(1, len(labels)):
        candidate = str(labels.iloc[i])
        if candidate == current:
            pending = None
            pending_count = 0
            out.iloc[i] = current
            continue

        if pending != candidate:
            pending = candidate
            pending_count = 1
        else:
            pending_count += 1

        if candidate == "Range":
            confirm_needed = int(p.get("range_entry_confirm_bars", 1))
        elif candidate == "HighVol":
            confirm_needed = int(p.get("highvol_entry_confirm_bars", 1))
        else:
            confirm_needed = int(p.get("trend_entry_confirm_bars", 1))

        if pending_count >= max(1, confirm_needed):
            current = candidate
            pending = None
            pending_count = 0

        out.iloc[i] = current

    return out


def apply_min_duration_filter(
    labels: pd.Series,
    extreme_highvol_mask: pd.Series,
    base_labels: pd.Series,
) -> pd.Series:
    p = REGIME_PARAMS
    filtered = labels.copy()
    n = len(filtered)
    i = 0
    while i < n:
        current = filtered.iloc[i]
        j = i + 1
        while j < n and filtered.iloc[j] == current:
            j += 1
        run_len = j - i
        if run_len < p["min_regime_bars"]:
            extreme_mask = extreme_highvol_mask.iloc[i:j]
            if extreme_mask.any():
                filtered.iloc[i:j] = "HighVol"
            else:
                fill_label = filtered.iloc[i - 1] if i > 0 else (filtered.iloc[j] if j < n else "Range")
                filtered.iloc[i:j] = fill_label
        i = j

    # Prevent month-long HighVol regimes; cap and then fall back to base trend/range labels.
    highvol_cap = int(p.get("highvol_max_bars", 0) or 0)
    if highvol_cap > 0:
        i = 0
        while i < n:
            current = filtered.iloc[i]
            j = i + 1
            while j < n and filtered.iloc[j] == current:
                j += 1
            if current == "HighVol":
                run_len = j - i
                if run_len > highvol_cap:
                    filtered.iloc[i + highvol_cap:j] = base_labels.iloc[i + highvol_cap:j].values
            i = j
    return filtered


def label_regimes(df: pd.DataFrame) -> pd.DataFrame:
    out = compute_indicators(df)
    base_labels = label_base(out)
    raw_labels = apply_hysteresis(label_raw(out))
    out["regime_raw"] = raw_labels
    p = REGIME_PARAMS
    extreme_highvol_mask = (
        (out["atr_ratio"] > p["highvol_extreme"])
        | (out["price_change_1h"].abs() > p["highvol_extreme_price_change_1h"])
    )
    out["regime"] = apply_min_duration_filter(raw_labels, extreme_highvol_mask, base_labels)
    out["confidence"] = 0.0
    regime_arr = out["regime"].values
    i = 0
    while i < len(regime_arr):
        j = i + 1
        while j < len(regime_arr) and regime_arr[j] == regime_arr[i]:
            j += 1
        run_len = j - i
        conf = min(1.0, run_len / REGIME_PARAMS["min_regime_bars"])
        out.iloc[i:j, out.columns.get_loc("confidence")] = round(conf, 3)
        i = j
    return out


def compute_stats(df: pd.DataFrame) -> Dict:
    total = len(df)
    stats: Dict = {"total_bars": total, "regimes": {}, "yearly": {}}
    for regime in ["Bull", "Bear", "Range", "HighVol"]:
        mask = df["regime"] == regime
        count = int(mask.sum())
        runs = []
        in_run = False
        start_idx = 0
        for k, value in enumerate(mask):
            if value and not in_run:
                in_run = True
                start_idx = k
            elif not value and in_run:
                in_run = False
                runs.append(k - start_idx)
        if in_run:
            runs.append(len(mask) - start_idx)
        stats["regimes"][regime] = {
            "count": count,
            "pct": round(count / total * 100, 1) if total else 0.0,
            "avg_duration_bars": round(float(np.mean(runs)), 1) if runs else 0,
            "avg_duration_hours": round(float(np.mean(runs)) * 0.25, 1) if runs else 0,
            "median_duration_bars": round(float(np.median(runs)), 1) if runs else 0,
            "median_duration_hours": round(float(np.median(runs)) * 0.25, 1) if runs else 0,
            "num_episodes": len(runs),
        }
    years = sorted(df.index.year.unique())
    for year in years:
        yearly_df = df[df.index.year == year]
        y_total = len(yearly_df)
        stats["yearly"][str(year)] = {
            r: round(int((yearly_df["regime"] == r).sum()) / y_total * 100, 1) if y_total else 0.0
            for r in ["Bull", "Bear", "Range", "HighVol"]
        }
    return stats


def build_html_chart(df: pd.DataFrame, stats: Dict, symbol: str = "BTCUSDT", timeframe: str = "15m") -> str:
    ohlc = (
        df[["open", "high", "low", "close"]]
        .resample("1h")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
        .dropna()
    )
    regime_resampled = df["regime"].resample("1h").last().reindex(ohlc.index).ffill()

    timestamps = [str(t) for t in ohlc.index]
    closes = ohlc["close"].tolist()

    blocks = []
    prev_r = None
    start_t = None
    for t, r in zip(timestamps, regime_resampled):
        if r != prev_r:
            if prev_r is not None:
                blocks.append({"regime": prev_r, "start": start_t, "end": t, "color": REGIME_COLORS[prev_r]})
            prev_r = r
            start_t = t
    if prev_r and timestamps:
        blocks.append({"regime": prev_r, "start": start_t, "end": timestamps[-1], "color": REGIME_COLORS[prev_r]})

    yearly_rows = ""
    for year, yd in stats["yearly"].items():
        yearly_rows += f"""
        <tr>
          <td>{year}</td>
          <td style=\"color:{REGIME_COLORS['Bull']}\">{yd['Bull']}%</td>
          <td style=\"color:{REGIME_COLORS['Bear']}\">{yd['Bear']}%</td>
          <td style=\"color:{REGIME_COLORS['Range']}\">{yd['Range']}%</td>
          <td style=\"color:{REGIME_COLORS['HighVol']}\">{yd['HighVol']}%</td>
        </tr>"""

    regime_summary = ""
    for r, rd in stats["regimes"].items():
        regime_summary += f"""
        <div class=\"regime-card\" style=\"border-left:4px solid {REGIME_COLORS[r]}\">
          <div class=\"regime-name\">{r}</div>
          <div class=\"regime-stat\">{rd['pct']}% ({rd['count']:,} bars)</div>
          <div class=\"regime-stat\">Avg {rd['avg_duration_hours']}h duration</div>
          <div class=\"regime-stat\">{rd['num_episodes']} episodes</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
<meta charset=\"UTF-8\">
<title>Regime Labels - {symbol} {timeframe}</title>
<script src=\"https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js\"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0d1117; color: #e6edf3; font-family: 'Segoe UI', sans-serif; padding: 24px; }}
  h1 {{ font-size: 20px; margin-bottom: 16px; color: #58a6ff; }}
  h2 {{ font-size: 14px; color: #8b949e; margin: 20px 0 10px; text-transform: uppercase; letter-spacing: 1px; }}
  .regime-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }}
  .regime-card {{ background: #161b22; padding: 14px 16px; border-radius: 8px; }}
  .regime-name {{ font-size: 16px; font-weight: 700; margin-bottom: 6px; }}
  .regime-stat {{ font-size: 12px; color: #8b949e; line-height: 1.8; }}
  .chart-wrap {{ background: #161b22; border-radius: 8px; padding: 16px; margin-bottom: 24px; }}
  table {{ width: 100%; border-collapse: collapse; background: #161b22; border-radius: 8px; overflow: hidden; }}
  th {{ background: #21262d; padding: 10px 14px; font-size: 12px; color: #8b949e; text-align: left; }}
  td {{ padding: 10px 14px; font-size: 13px; border-top: 1px solid #21262d; }}
  .params {{ background: #161b22; border-radius: 8px; padding: 16px; font-size: 12px; color: #8b949e; }}
  .params span {{ color: #e6edf3; }}
</style>
</head>
<body>
<h1>Regime Labels: {symbol} {timeframe}</h1>
<h2>Distribution</h2>
<div class=\"regime-grid\">{regime_summary}</div>
<h2>Price + Regime (1h resample)</h2>
<div class=\"chart-wrap\"><canvas id=\"priceChart\" height=\"120\"></canvas></div>
<h2>Yearly Regime Ratio</h2>
<table>
  <thead><tr><th>Year</th><th>Bull</th><th>Bear</th><th>Range</th><th>HighVol</th></tr></thead>
  <tbody>{yearly_rows}</tbody>
</table>
<h2 style=\"margin-top:20px\">Parameters</h2>
<div class=\"params\">
  EMA: <span>{REGIME_PARAMS['trend_ema_period']}</span> |
  Lookback: <span>{REGIME_PARAMS['trend_lookback']}</span> |
  Bull/Bear: <span>±{REGIME_PARAMS['bull_threshold']}%</span> |
  Range |slope|: <span>{REGIME_PARAMS['range_slope_abs_max']}%</span> |
  Range eff<=: <span>{REGIME_PARAMS['range_efficiency_max']}</span> |
  Range ATR<=: <span>{REGIME_PARAMS['range_atr_ratio_max']}%</span> |
  ATR: <span>{REGIME_PARAMS['atr_period']}</span> |
  HV ATR: <span>{REGIME_PARAMS['highvol_atr_threshold']}%</span> |
  HV |1hΔ|: <span>{REGIME_PARAMS['highvol_price_change_1h']}%</span> |
  Extreme ATR: <span>{REGIME_PARAMS['highvol_extreme']}%</span> |
  Extreme |1hΔ|: <span>{REGIME_PARAMS['highvol_extreme_price_change_1h']}%</span> |
  MinDuration: <span>{REGIME_PARAMS['min_regime_bars']}</span> |
  HighVolMax: <span>{REGIME_PARAMS['highvol_max_bars']}</span> |
  Confirm(range/trend/hv): <span>{REGIME_PARAMS['range_entry_confirm_bars']}/{REGIME_PARAMS['trend_entry_confirm_bars']}/{REGIME_PARAMS['highvol_entry_confirm_bars']}</span>
</div>
<script>
const timestamps = {json.dumps(timestamps)};
const closes = {json.dumps([round(c, 2) for c in closes])};
const blocks = {json.dumps(blocks)};
const ctx = document.getElementById('priceChart').getContext('2d');
const regimeBgPlugin = {{
  id: 'regimeBg',
  beforeDraw(chart) {{
    const {{ctx, scales, chartArea}} = chart;
    if (!chartArea) return;
    const xScale = scales.x;
    ctx.save();
    blocks.forEach(b => {{
      const x1 = xScale.getPixelForValue(b.start);
      const x2 = xScale.getPixelForValue(b.end);
      if (x2 < chartArea.left || x1 > chartArea.right) return;
      ctx.fillStyle = b.color + '33';
      ctx.fillRect(Math.max(x1, chartArea.left), chartArea.top, Math.min(x2, chartArea.right) - Math.max(x1, chartArea.left), chartArea.bottom - chartArea.top);
    }});
    ctx.restore();
  }}
}};
new Chart(ctx, {{
  type: 'line',
  plugins: [regimeBgPlugin],
  data: {{ labels: timestamps, datasets: [{{ data: closes, borderColor: '#58a6ff', borderWidth: 1, pointRadius: 0, tension: 0.1 }}] }},
  options: {{
    responsive: true,
    animation: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ ticks: {{ maxTicksLimit: 12, color: '#8b949e', font: {{ size: 10 }} }}, grid: {{ color: '#21262d' }} }},
      y: {{ ticks: {{ color: '#8b949e', font: {{ size: 10 }} }}, grid: {{ color: '#21262d' }} }}
    }}
  }}
}});
</script>
</body>
</html>"""


def resolve_out_root(out_dir: Optional[str]) -> Path:
    if not out_dir:
        return PROJECT_ROOT / "tmp" / "regime_runs"
    candidate = (PROJECT_ROOT / out_dir).resolve()
    root = PROJECT_ROOT.resolve()
    if not str(candidate).startswith(str(root)):
        raise ValueError("out_dir must be inside project root.")
    return candidate


def _ohlcv_disk_cache_path(
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str,
) -> Path:
    safe_symbol = str(symbol).upper().replace("/", "").replace(" ", "")
    cache_name = f"{safe_symbol}_{timeframe}_{start_date}_{end_date}.parquet"
    return PROJECT_ROOT / "tmp" / "cache" / "ohlcv" / cache_name


def run_regime_labeler(
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str,
    out_dir: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Dict:
    logs = []
    started_at = datetime.utcnow()
    if timeframe != "15m":
        raise ValueError("Only 15m timeframe is supported in v1 regime tab.")

    start_ms = parse_date_to_ms(start_date, end_of_day=False)
    end_ms = parse_date_to_ms(end_date, end_of_day=True)
    if start_ms is None or end_ms is None or end_ms <= start_ms:
        raise ValueError("Invalid date range. Use YYYY-MM-DD and start < end.")

    cache_path = _ohlcv_disk_cache_path(symbol, timeframe, start_date, end_date)
    df: pd.DataFrame
    cache_hit_disk = False
    if cache_path.exists():
        cache_hit_disk = True
        logs.append(f"[cache] hit: {cache_path.relative_to(PROJECT_ROOT)}")
        df = pd.read_parquet(cache_path)
    else:
        logs.append("[cache] miss: fetching OHLCV from provider")
        step_ms = 900_000
        expected_bars = int((end_ms - start_ms) / step_ms) + 2
        df = fetch_ohlcv_dataframe(
            symbol=symbol,
            interval=timeframe,
            limit=expected_bars,
            start_ms=start_ms,
            end_ms=end_ms,
        )
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            df.to_parquet(cache_path)
            logs.append(f"[cache] saved: {cache_path.relative_to(PROJECT_ROOT)}")
        except Exception:
            logs.append("[cache] save skipped: parquet write failed")

    if df.empty:
        raise RuntimeError("No market data found for the given range.")
    logs.append(f"[data] loaded rows: {len(df):,}")

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    logs.append(f"[data] normalized rows: {len(df):,}")

    labeled = label_regimes(df)
    stats = compute_stats(labeled)
    logs.append("[labeler] regime labeling complete")

    out_root = resolve_out_root(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    effective_run_id = run_id or datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    run_dir = out_root / effective_run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    parquet_path = run_dir / ARTIFACT_MAP["parquet"]
    stats_path = run_dir / ARTIFACT_MAP["stats"]
    chart_path = run_dir / ARTIFACT_MAP["chart"]

    parquet_frame = labeled[
        [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "ema",
            "ema_slope",
            "atr",
            "atr_ratio",
            "price_change_1h",
            "efficiency_20",
            "regime_raw",
            "regime",
            "confidence",
        ]
    ]
    try:
        parquet_frame.to_parquet(parquet_path)
    except ImportError as exc:
        raise RuntimeError(
            "Parquet engine not installed. Install `pyarrow` or `fastparquet` to export regime_labels.parquet."
        ) from exc
    stats_payload = {
        "symbol": symbol,
        "timeframe": timeframe,
        "start_date": start_date,
        "end_date": end_date,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "params": REGIME_PARAMS,
        "logs": [],
        "diagnostics": {
            "cache_hit_disk": cache_hit_disk,
            "cache_path": str(cache_path.relative_to(PROJECT_ROOT)),
            "validation_window": f"{DEFAULT_VALIDATION_START} ~ {DEFAULT_VALIDATION_END}",
            "duration_sec": round((datetime.utcnow() - started_at).total_seconds(), 3),
        },
        **stats,
    }
    chart_path.write_text(build_html_chart(labeled, stats, symbol=symbol, timeframe=timeframe), encoding="utf-8")
    logs.append(f"[artifact] parquet: {parquet_path.relative_to(PROJECT_ROOT)}")
    logs.append(f"[artifact] stats: {stats_path.relative_to(PROJECT_ROOT)}")
    logs.append(f"[artifact] chart: {chart_path.relative_to(PROJECT_ROOT)}")
    logs.append(f"[done] run_id={effective_run_id}")
    stats_payload["logs"] = logs
    stats_path.write_text(json.dumps(stats_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "run_id": effective_run_id,
        "base_dir": str(out_root.relative_to(PROJECT_ROOT)),
        "stats": stats_payload,
        "logs": logs,
        "artifact_paths": {
            "parquet": str(parquet_path.relative_to(PROJECT_ROOT)),
            "stats": str(stats_path.relative_to(PROJECT_ROOT)),
            "chart": str(chart_path.relative_to(PROJECT_ROOT)),
        },
    }
