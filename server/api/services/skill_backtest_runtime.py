from __future__ import annotations

import importlib.util
import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from server.api.services.market_data import fetch_ohlcv_dataframe, parse_date_to_ms, sanitize_symbol
from server.api.services.supabase_client import SupabaseManager

PROJECT_ROOT = Path(__file__).resolve().parents[3]

LEGACY_STRATEGY_ALIAS: Dict[str, str] = {
    "optPredator": "ema_crossover",
    "optQuantum": "macd",
    "optWhale": "breakout",
    "optApexV2": "rsi_reversal",
}

LEGACY_STRATEGY_LABELS: Dict[str, str] = {
    "optPredator": "MINARA V2",
    "optQuantum": "ARBITER V1",
    "optWhale": "NIM-ALPHA",
    "optApexV2": "CHIMERA-β",
}

DEFAULT_PARAMS: Dict[str, Dict[str, Any]] = {
    "donchian_breakout_atr": {
        "period": 15,
        "atr_period": 14,
        "range_bars": 5,
        "range_atr_mult": 6.0,
        "sl_atr_mult": 1.5,
        "tp_atr_mult": 3.0,
    }
}

TF_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
}

_supabase_manager: Optional[SupabaseManager] = None
_supabase_unavailable = False
_seed_attempted = False

# Simple in-memory cache for strategies
_STRATEGY_CACHE: List[Dict[str, Any]] = []
_STRATEGY_CACHE_EXPIRY: float = 0
_CACHE_TTL = 300  # 5 minutes


def _get_supabase_manager() -> Optional[SupabaseManager]:
    global _supabase_manager, _supabase_unavailable
    if _supabase_unavailable:
        return None
    if _supabase_manager is not None:
        return _supabase_manager

    try:
        _supabase_manager = SupabaseManager()
        return _supabase_manager
    except Exception as exc:
        print(f"Supabase disabled for strategy runtime: {exc}")
        _supabase_unavailable = True
        return None


def resolve_skill_dir() -> Path:
    candidates = [
        PROJECT_ROOT / "server" / "backtesting-trading-strategies",
        PROJECT_ROOT / ".agents" / "skills" / "backtesting-trading-strategies",
    ]
    for candidate in candidates:
        if (candidate / "scripts" / "backtest.py").exists():
            return candidate
    raise RuntimeError(
        "Backtesting skill not found. Expected under "
        "server/backtesting-trading-strategies or .agents/skills/backtesting-trading-strategies"
    )


def _load_module(module_name: str, module_file: Path):
    spec = importlib.util.spec_from_file_location(module_name, module_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module: {module_file}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_skill_modules():
    skill_dir = resolve_skill_dir()
    scripts_dir = skill_dir / "scripts"

    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    # Load as canonical module name so backtest.py imports the same strategies module.
    strategies_mod = _load_module("strategies", scripts_dir / "strategies.py")
    backtest_mod = _load_module("skill_backtest_runtime_api", scripts_dir / "backtest.py")
    return skill_dir, scripts_dir, backtest_mod, strategies_mod


def _resolve_local_key(strategy_key: str, available_keys: List[str]) -> str:
    if strategy_key in available_keys:
        return strategy_key
    alias_target = LEGACY_STRATEGY_ALIAS.get(strategy_key)
    if alias_target and alias_target in available_keys:
        return alias_target
    return strategy_key


def _extract_class_block(strategies_file: Path, class_name: str) -> Optional[str]:
    if not strategies_file.exists():
        return None
    text = strategies_file.read_text(encoding="utf-8")
    pattern = rf"(class\s+{re.escape(class_name)}\(Strategy\):[\s\S]*?)(?=\nclass\s+\w+\(Strategy\):|\n# Strategy registry|\Z)"
    match = re.search(pattern, text)
    if not match:
        return text
    return match.group(1).rstrip() + "\n"


def _build_local_catalog(scripts_dir: Path, strategies_mod: Any) -> List[Dict[str, Any]]:
    registry: Dict[str, Any] = dict(getattr(strategies_mod, "STRATEGIES", {}) or {})
    descriptions: Dict[str, str] = dict(strategies_mod.list_strategies()) if hasattr(strategies_mod, "list_strategies") else {}

    out: List[Dict[str, Any]] = []

    for legacy_key, native_key in LEGACY_STRATEGY_ALIAS.items():
        if native_key not in registry:
            continue
        class_name = registry[native_key].__class__.__name__
        out.append(
            {
                "key": legacy_key,
                "label": LEGACY_STRATEGY_LABELS.get(legacy_key, legacy_key),
                "description": f"Legacy alias of `{native_key}`",
                "timeframe": "1h",
                "default_timeframe": "1h",
                "supported_timeframes": ["1m", "5m", "15m", "1h", "4h"],
                "native_key": native_key,
                "class_name": class_name,
                "source": "local",
            }
        )

    for key, strategy_obj in registry.items():
        out.append(
            {
                "key": key,
                "label": key.replace("_", " ").title(),
                "description": descriptions.get(key, ""),
                "timeframe": "1h",
                "default_timeframe": "1h",
                "supported_timeframes": ["1m", "5m", "15m", "1h", "4h"],
                "native_key": key,
                "class_name": strategy_obj.__class__.__name__,
                "source": "local",
            }
        )

    return out


def _get_local_strategy_source(strategy_key: str, scripts_dir: Path, strategies_mod: Any) -> Optional[str]:
    registry: Dict[str, Any] = dict(getattr(strategies_mod, "STRATEGIES", {}) or {})
    target_key = _resolve_local_key(strategy_key, list(registry.keys()))
    strategy_obj = registry.get(target_key)
    if strategy_obj is None:
        return None

    class_name = strategy_obj.__class__.__name__
    return _extract_class_block(scripts_dir / "strategies.py", class_name)


def seed_local_strategies_to_db(force: bool = False) -> Dict[str, int]:
    global _seed_attempted

    if _seed_attempted and not force:
        return {"inserted": 0, "skipped": 0, "failed": 0}

    manager = _get_supabase_manager()
    if manager is None:
        _seed_attempted = True
        return {"inserted": 0, "skipped": 0, "failed": 0}

    _, scripts_dir, _, strategies_mod = _load_skill_modules()
    local_catalog = _build_local_catalog(scripts_dir, strategies_mod)

    inserted = 0
    skipped = 0
    failed = 0

    for item in local_catalog:
        key = str(item.get("key"))
        existing = manager.get_strategy_by_key(strategy_key=key, source="system")
        if existing:
            skipped += 1
            continue

        code = _get_local_strategy_source(key, scripts_dir, strategies_mod)
        if not code:
            failed += 1
            continue

        params = {
            "strategy_key": key,
            "native_key": item.get("native_key") or key,
            "display_name": item.get("label") or key,
            "description": item.get("description") or "",
            "timeframe": item.get("timeframe") or "1h",
            "supported_timeframes": item.get("supported_timeframes") or ["1h"],
            "backtest_params": dict(DEFAULT_PARAMS.get(str(item.get("native_key") or key), {})),
        }

        strategy_id = manager.save_system_strategy(
            strategy_key=key,
            code=code,
            params=params,
            rationale="Seeded from local backtesting strategy catalog",
        )
        if strategy_id:
            inserted += 1
        else:
            failed += 1

    _seed_attempted = True
    return {"inserted": inserted, "skipped": skipped, "failed": failed}


def _build_db_catalog() -> List[Dict[str, Any]]:
    manager = _get_supabase_manager()
    if manager is None:
        return []

    rows = manager.list_strategies(limit=1000)
    if not rows:
        return []

    out: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for row in rows:
        if row.get("source") != "system":
            continue

        params = row.get("params") or {}
        if not isinstance(params, dict):
            continue

        key = str(params.get("strategy_key") or "").strip()
        if not key or key in seen:
            continue

        code = row.get("code")
        if not code:
            continue

        out.append(
            {
                "key": key,
                "label": str(params.get("display_name") or key),
                "description": str(params.get("description") or row.get("rationale") or ""),
                "timeframe": str(params.get("timeframe") or "1h"),
                "default_timeframe": str(params.get("timeframe") or "1h"),
                "supported_timeframes": list(params.get("supported_timeframes") or ["1h"]),
                "native_key": str(params.get("native_key") or key),
                "class_name": None,
                "source": str(row.get("source") or "db"),
                "params": params,
            }
        )
        seen.add(key)

    return out


def list_skill_strategies() -> List[Dict[str, Any]]:
    global _STRATEGY_CACHE, _STRATEGY_CACHE_EXPIRY
    
    import time
    now = time.time()
    
    # Return cached data if valid
    if _STRATEGY_CACHE and now < _STRATEGY_CACHE_EXPIRY:
        return _STRATEGY_CACHE

    # Seed once so local strategies become DB rows if DB is configured.
    seed_local_strategies_to_db(force=False)

    db_catalog = _build_db_catalog()
    if db_catalog:
        _STRATEGY_CACHE = db_catalog
        _STRATEGY_CACHE_EXPIRY = now + _CACHE_TTL
        return db_catalog

    _, scripts_dir, _, strategies_mod = _load_skill_modules()
    local_catalog = _build_local_catalog(scripts_dir, strategies_mod)
    
    _STRATEGY_CACHE = local_catalog
    _STRATEGY_CACHE_EXPIRY = now + _CACHE_TTL
    return local_catalog


def resolve_strategy_key(strategy_key: str, available_keys: List[str]) -> str:
    return _resolve_local_key(strategy_key, available_keys)


def get_strategy_source(strategy_key: str) -> Optional[str]:
    manager = _get_supabase_manager()
    if manager is not None:
        row = manager.get_strategy_by_key(strategy_key=strategy_key)
        if row and row.get("code"):
            return str(row.get("code"))

    _, scripts_dir, _, strategies_mod = _load_skill_modules()
    return _get_local_strategy_source(strategy_key, scripts_dir, strategies_mod)


def _register_db_strategy(strategies_mod: Any, strategy_key: str, code: str) -> Tuple[str, str]:
    base_strategy_cls = getattr(strategies_mod, "Strategy")
    signal_cls = getattr(strategies_mod, "Signal", None)

    exec_globals: Dict[str, Any] = {
        "__name__": f"db_strategy_runtime_{strategy_key}",
        "Strategy": base_strategy_cls,
        "Signal": signal_cls,
        "pd": pd,
        "np": np,
    }
    exec_locals: Dict[str, Any] = {}
    exec(code, exec_globals, exec_locals)

    candidates: List[type] = []
    for obj in exec_locals.values():
        if isinstance(obj, type) and issubclass(obj, base_strategy_cls) and obj is not base_strategy_cls:
            candidates.append(obj)

    if not candidates:
        raise RuntimeError(f"No Strategy subclass found in DB code for '{strategy_key}'")

    strategy_cls = candidates[0]
    instance = strategy_cls()

    runtime_key = f"db::{strategy_key}"
    strategies_mod.STRATEGIES[runtime_key] = instance
    return runtime_key, strategy_cls.__name__


def _trade_to_payload(trade: Any) -> Dict[str, Any]:
    direction = "LONG" if str(trade.direction).lower() == "long" else "SHORT"
    return {
        "type": direction,
        "time": pd.Timestamp(trade.exit_time).isoformat(),
        "exitReason": "signal_or_risk",
        "entry": float(trade.entry_price),
        "exit": float(trade.exit_price),
        "sl": 0.0,
        "tp": 0.0,
        "posSize": float(trade.size),
        "profitPct": f"{float(trade.pnl_pct):+.2f}%",
        "profitAmt": float(trade.pnl),
    }


def _markers_from_trade(trade: Any) -> List[Dict[str, Any]]:
    is_long = str(trade.direction).lower() == "long"
    return [
        {
            "time": int(pd.Timestamp(trade.entry_time).timestamp()),
            "position": "belowBar" if is_long else "aboveBar",
            "color": "#4ade80" if is_long else "#fb7185",
            "shape": "arrowUp" if is_long else "arrowDown",
            "text": "L" if is_long else "S",
        },
        {
            "time": int(pd.Timestamp(trade.exit_time).timestamp()),
            "position": "aboveBar" if is_long else "belowBar",
            "color": "#22c55e" if float(trade.pnl) >= 0 else "#ef4444",
            "shape": "circle",
            "text": "X",
        },
    ]


def _candles_payload(frame: pd.DataFrame) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for idx, row in frame.iterrows():
        out.append(
            {
                "time": int(pd.Timestamp(idx).timestamp()),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row.get("volume", 0.0) or 0.0),
            }
        )
    return out


def _compute_side_stats(trades: List[Any], side: str) -> Tuple[int, float, float, float]:
    selected = [t for t in trades if str(t.direction).lower() == side.lower()]
    pnls = [float(t.pnl) for t in selected]
    wins = [x for x in pnls if x > 0]
    losses = [x for x in pnls if x < 0]

    win_rate = (len(wins) / len(selected) * 100.0) if selected else 0.0
    gross_profit = sum(wins)
    gross_loss = sum(losses)
    if gross_loss < 0:
        pf = gross_profit / abs(gross_loss)
    else:
        pf = gross_profit if gross_profit > 0 else 0.0
    return len(selected), win_rate, sum(pnls), pf


def run_skill_backtest(
    symbol: str,
    interval: str,
    strategy: str,
    leverage: float,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    include_candles: bool = True,
    code: Optional[str] = None,
) -> Dict[str, Any]:
    # Ensure seed attempt before execution.
    seed_local_strategies_to_db(force=False)

    skill_dir, _, backtest_mod, strategies_mod = _load_skill_modules()

    catalog = {item["key"]: item for item in list_skill_strategies()}
    available = list(catalog.keys())
    
    # If raw code is provided, we register it as a temporary runtime strategy
    if code:
        try:
            resolved_strategy = f"custom_{hash(code) % 10000}"
            runtime_strategy_name, runtime_class_name = _register_db_strategy(
                strategies_mod=strategies_mod,
                strategy_key=resolved_strategy,
                code=code,
            )
            runtime_strategy_source = "custom_live"
            runtime_params = dict(DEFAULT_PARAMS.get("donchian_breakout_atr", {})) # Fallback params
        except Exception as exc:
            return {"success": False, "error": f"Failed to compile custom code: {exc}"}
    else:
        resolved_strategy = _resolve_local_key(strategy, available)
        if resolved_strategy not in available:
            return {"success": False, "error": f"Invalid strategy: {strategy}"}

        manager = _get_supabase_manager()
        db_row = manager.get_strategy_by_key(strategy_key=resolved_strategy) if manager else None

        runtime_strategy_name = resolved_strategy
        runtime_strategy_source = "local"
        runtime_class_name: Optional[str] = None
        runtime_params: Dict[str, Any] = {}

        if db_row and db_row.get("code"):
            try:
                runtime_strategy_name, runtime_class_name = _register_db_strategy(
                    strategies_mod=strategies_mod,
                    strategy_key=resolved_strategy,
                    code=str(db_row.get("code")),
                )
                runtime_strategy_source = str(db_row.get("source") or "db")
                db_params = db_row.get("params") or {}
                if isinstance(db_params, dict):
                    runtime_params = dict(db_params.get("backtest_params") or {})
            except Exception as exc:
                return {
                    "success": False,
                    "error": f"Failed to compile DB strategy '{resolved_strategy}': {exc}",
                }

        if not runtime_params:
            native_key = str(catalog.get(resolved_strategy, {}).get("native_key") or resolved_strategy)
            runtime_params = dict(DEFAULT_PARAMS.get(native_key, {}))

    try:
        start_ms = parse_date_to_ms(start_date, end_of_day=False)
        end_ms = parse_date_to_ms(end_date, end_of_day=True)
    except ValueError:
        return {"success": False, "error": "Invalid date format. Use YYYY-MM-DD."}

    if start_ms is not None and end_ms is not None and start_ms >= end_ms:
        return {"success": False, "error": "start_date must be before end_date"}

    try:
        market_df = fetch_ohlcv_dataframe(
            symbol=symbol,
            interval=interval,
            limit=2000,
            start_ms=start_ms,
            end_ms=end_ms,
        )
    except Exception as exc:
        return {"success": False, "error": f"OHLCV fetch failed: {exc}"}

    if market_df.empty:
        return {"success": False, "error": "No market data"}

    data = market_df.copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"]).dt.tz_localize(None)
    data = data.set_index("timestamp")[["open", "high", "low", "close", "volume"]]
    data.attrs["symbol"] = sanitize_symbol(symbol)

    try:
        result = backtest_mod.run_backtest(
            strategy_name=runtime_strategy_name,
            data=data,
            initial_capital=10_000.0,
            params=runtime_params,
            commission=0.001,
            slippage=0.0005,
            risk_settings={"max_position_size": min(0.95, max(0.1, leverage / 20.0))},
        )
    except Exception as exc:
        return {
            "success": False,
            "error": f"Skill backtest failed: {exc}",
            "skill_dir": str(skill_dir),
        }

    trades = list(result.trades or [])
    trade_payload = [_trade_to_payload(t) for t in trades]
    markers: List[Dict[str, Any]] = []
    for t in trades:
        markers.extend(_markers_from_trade(t))

    candles = _candles_payload(data) if include_candles else []

    pnl_values = [float(t.pnl) for t in trades]
    wins = [x for x in pnl_values if x > 0]
    losses = [x for x in pnl_values if x < 0]

    long_count, _, long_pnl, long_pf = _compute_side_stats(trades, "long")
    short_count, _, short_pnl, short_pf = _compute_side_stats(trades, "short")

    if len(data) > 1:
        buy_hold = ((float(data["close"].iloc[-1]) / float(data["close"].iloc[0])) - 1.0) * 100.0
    else:
        buy_hold = 0.0

    avg_bars = 0.0
    tf_sec = TF_SECONDS.get(interval, 0)
    if tf_sec > 0 and trades:
        bars = []
        for t in trades:
            sec = (pd.Timestamp(t.exit_time) - pd.Timestamp(t.entry_time)).total_seconds()
            bars.append(max(1.0, sec / tf_sec))
        avg_bars = sum(bars) / len(bars)

    total_pnl = float(result.final_capital - result.initial_capital)
    total_return = float(getattr(result, "total_return", 0.0))
    max_drawdown = abs(float(getattr(result, "max_drawdown", 0.0)))
    sharpe_ratio = float(getattr(result, "sharpe_ratio", 0.0))
    sortino_ratio = float(getattr(result, "sortino_ratio", 0.0))
    calmar_ratio = float(getattr(result, "calmar_ratio", 0.0))

    raw_pf = float(getattr(result, "profit_factor", 0.0))
    if math.isfinite(raw_pf):
        profit_factor = raw_pf
    else:
        profit_factor = 999.0

    return {
        "success": True,
        "framework": "backtesting-trading-strategies",
        "symbol": sanitize_symbol(symbol),
        "interval": interval,
        "strategy": strategy,
        "strategy_resolved": resolved_strategy,
        "strategy_runtime": {
            "source": runtime_strategy_source,
            "class_name": runtime_class_name,
            "strategy_name": runtime_strategy_name,
        },
        "candles": candles,
        "trades": trade_payload,
        "markers": markers,
        "results": {
            "total_pnl": total_pnl,
            "total_return": total_return,
            "win_rate": float(getattr(result, "win_rate", 0.0)),
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "calmar_ratio": calmar_ratio,
            "profit_factor": profit_factor,
            "total_trades": int(getattr(result, "total_trades", 0)),
            "best_trade": max(pnl_values) if pnl_values else 0.0,
            "worst_trade": min(pnl_values) if pnl_values else 0.0,
            "win_count": len(wins),
            "loss_count": len(losses),
            "avg_profit": float(getattr(result, "avg_win", 0.0)),
            "avg_loss": abs(float(getattr(result, "avg_loss", 0.0))),
            "max_consecutive_wins": int(getattr(result, "max_consecutive_wins", 0)),
            "max_consecutive_losses": int(getattr(result, "max_consecutive_losses", 0)),
            "avg_bars": avg_bars,
            "long_count": long_count,
            "short_count": short_count,
            "long_return": long_pnl,
            "short_return": short_pnl,
            "long_pf": long_pf,
            "short_pf": short_pf,
            "buy_hold": buy_hold,
            "alpha": total_return - buy_hold,
            "expected_return": float(getattr(result, "expectancy", 0.0)),
            "total_fees": 0.0,
        },
        "meta": {
            "skill_dir": str(skill_dir),
            "start_date": start_date,
            "end_date": end_date,
        },
    }
