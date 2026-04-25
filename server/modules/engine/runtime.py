from __future__ import annotations

import importlib.util
import inspect
import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from server.shared.market.provider import fetch_ohlcv_dataframe, parse_date_to_ms, sanitize_symbol
from server.shared.db.supabase import SupabaseManager
from server.modules.backtest.backtest_engine import BacktestEngine, RealisticSimulator, strategy_from_code, compute_metrics

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Legacy mappings removed for clean environment.
LEGACY_STRATEGY_ALIAS: Dict[str, str] = {}
LEGACY_STRATEGY_LABELS: Dict[str, str] = {}
DEFAULT_PARAMS: Dict[str, Dict[str, Any]] = {}

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


def invalidate_strategy_cache() -> None:
    """Invalidate in-memory strategy catalog cache."""
    global _STRATEGY_CACHE, _STRATEGY_CACHE_EXPIRY
    _STRATEGY_CACHE = []
    _STRATEGY_CACHE_EXPIRY = 0


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


def resolve_skill_dir() -> Optional[Path]:
    candidates = [
        PROJECT_ROOT / "server" / "backtesting-trading-strategies",
        PROJECT_ROOT / ".agents" / "skills" / "backtesting-trading-strategies",
    ]
    for candidate in candidates:
        if (candidate / "scripts" / "backtest.py").exists():
            return candidate
    return None


def _load_module(module_name: str, module_file: Path):
    spec = importlib.util.spec_from_file_location(module_name, module_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module: {module_file}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_skill_modules():
    # 신형 엔진 체제에서는 스킬 모듈을 동적으로 로드할 필요가 없습니다.
    # 이전 코드와의 호환성을 위해 Path만 반환합니다.
    return None, None, None, None


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

    # Pure AI strategies are mapped directly to registry keys
    for key, strategy_obj in registry.items():
        if strategy_obj is None:
            continue
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


# -------------------------------------------------------------------------
# [Helper] 로컬 전략 소스 추출: 파일에서 특정 전략 클래스의 코드 블록만 읽어옴
# -------------------------------------------------------------------------
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
        params = row.get("params") or {}
        if not isinstance(params, dict):
            continue

        # [IMPROVEMENT] name 컬럼이 있는 전략만 표시 (사용자 요청)
        # DB 컬럼의 'name'을 먼저 확인하고, 없으면 params 내의 'display_name' 확인
        strategy_name = row.get("name") or params.get("display_name")
        if not strategy_name or strategy_name.strip() == "":
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
                "label": str(strategy_name), # 정제된 이름을 라벨로 사용
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


# -------------------------------------------------------------------------
# [Core] 전략 목록 나열: DB와 로컬에 있는 모든 실행 가능 전략을 통합하여 반환
# -------------------------------------------------------------------------
def list_skill_strategies() -> List[Dict[str, Any]]:
    global _STRATEGY_CACHE, _STRATEGY_CACHE_EXPIRY
    
    import time
    now = time.time()
    
    # Return cached data if valid
    if _STRATEGY_CACHE and now < _STRATEGY_CACHE_EXPIRY:
        return _STRATEGY_CACHE

    # [REMOVED] seed_local_strategies_to_db(force=False)
    # 더 이상 로컬 레거시 전략을 자동으로 DB에 주입하지 않습니다. (사용자 요청)

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


def _build_legacy_signal_adapter(
    strategy_key: str,
    base_strategy_cls: type,
    legacy_cls: type,
    signal_cls: Any,
) -> Optional[type]:
    generate_signal_fn = getattr(legacy_cls, "generate_signal", None)
    if signal_cls is None or not callable(generate_signal_fn):
        return None

    class LegacySignalAdapter(legacy_cls):  # type: ignore[misc, valid-type]
        name = str(getattr(legacy_cls, "name", strategy_key) or strategy_key)
        lookback = int(getattr(legacy_cls, "lookback", 1) or 1)

        def __init__(self) -> None:
            super().__init__()
            self._runtime_last_target = 0

        def generate_signals(self, data: pd.DataFrame, params: Dict[str, Any]) -> Any:
            try:
                raw_value = float(self.generate_signal(data))
            except Exception:
                raw_value = 0.0

            target = 1 if raw_value > 0 else (-1 if raw_value < 0 else 0)
            prev = int(getattr(self, "_runtime_last_target", 0))
            self._runtime_last_target = target

            if target > 0:
                if prev < 0:
                    return signal_cls(entry=True, exit=True, direction="long")
                if prev == 0:
                    return signal_cls(entry=True, direction="long")
                return signal_cls()

            if target < 0:
                if prev > 0:
                    return signal_cls(entry=True, exit=True, direction="short")
                if prev == 0:
                    return signal_cls(entry=True, direction="short")
                return signal_cls()

            if prev != 0:
                return signal_cls(exit=True)
            return signal_cls()

    LegacySignalAdapter.__name__ = f"{legacy_cls.__name__}BacktestAdapter"
    if not issubclass(LegacySignalAdapter, base_strategy_cls):
        return None
    return LegacySignalAdapter


# -------------------------------------------------------------------------
# [Core] DB 전략 등록: DB에 저장된 전략 코드를 실행 가능한 클래스로 동적 컴파일
# -------------------------------------------------------------------------
def _register_db_strategy(strategies_mod: Any, strategy_key: str, code: str) -> Tuple[str, str]:
    base_strategy_cls = getattr(strategies_mod, "Strategy")
    signal_cls = getattr(strategies_mod, "Signal", None)

    exec_globals: Dict[str, Any] = {
        "__name__": f"db_strategy_runtime_{strategy_key}",
        "Strategy": base_strategy_cls,
        # Backward compatibility for DB-stored strategy templates that inherit
        # from StrategyInterface instead of Strategy.
        "StrategyInterface": base_strategy_cls,
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

    strategy_cls: Optional[type] = None
    instance: Any = None
    candidate_errors: List[str] = []

    for candidate_cls in candidates:
        cls_to_init: type = candidate_cls
        if inspect.isabstract(candidate_cls):
            adapter_cls = _build_legacy_signal_adapter(
                strategy_key=strategy_key,
                base_strategy_cls=base_strategy_cls,
                legacy_cls=candidate_cls,
                signal_cls=signal_cls,
            )
            if adapter_cls is None:
                candidate_errors.append(f"{candidate_cls.__name__}: abstract class")
                continue
            cls_to_init = adapter_cls
        try:
            instance = cls_to_init()
            strategy_cls = cls_to_init
            break
        except Exception as exc:
            candidate_errors.append(f"{cls_to_init.__name__}: {exc}")

    if strategy_cls is None or instance is None:
        details = "; ".join(candidate_errors) if candidate_errors else "no valid Strategy subclass found"
        raise RuntimeError(
            f"Failed to instantiate strategy '{strategy_key}': {details}"
        )

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


# -------------------------------------------------------------------------
# [Main] 백테스트 엔진 실행: 데이터 수집, 전략 컴파일, 실행 및 결과 집계 총괄
# -------------------------------------------------------------------------
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
    # 1. 전략 소스 확보 (제공된 코드 또는 DB/로컬 조회)
    if code:
        strat_code = code
        resolved_strategy = f"custom_ai_strategy"
        source = "live"
    else:
        # DB에서 전략 코드 가져오기 시도
        manager = _get_supabase_manager()
        row = manager.get_strategy_by_key(strategy_key=strategy) if manager else None
        if row and row.get("code"):
            strat_code = str(row.get("code"))
            resolved_strategy = strategy
            source = "db"
        else:
            return {"success": False, "error": f"Strategy code not found for '{strategy}'"}

    # 2. 데이터 수집
    try:
        start_ms = parse_date_to_ms(start_date, end_of_day=False)
        end_ms = parse_date_to_ms(end_date, end_of_day=True)
        market_df = fetch_ohlcv_dataframe(
            symbol=symbol,
            interval=interval,
            limit=10000,
            start_ms=start_ms,
            end_ms=end_ms,
        )
    except Exception as exc:
        return {"success": False, "error": f"Data fetch failed: {exc}"}

    if market_df.empty:
        return {"success": False, "error": "No market data found for the given range"}

    df = market_df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp")

    # 3. 전략 실행 (Signal 생성)
    try:
        strategy_fn = strategy_from_code(strat_code)
        # 신형 엔진의 strategy_fn(train_df, test_df) 형식을 맞추기 위해 더미 데이터 제공
        train_df = df.iloc[:len(df)//2]  # 대략적인 절반
        test_df = df
        signal = strategy_fn(train_df, test_df)
    except Exception as exc:
        return {"success": False, "error": f"Strategy execution error: {exc}"}

    # 4. 신형 시뮬레이터 구동
    sim = RealisticSimulator(max_position=min(1.0, leverage/10.0))
    # [IMPORTANT] 새로 추가된 롱/숏 수익률 및 비용 데이터 캡처
    rets, n_trades, trade_results, costs, l_rets, s_rets = sim.run(df, signal)
    
    # 벤치마크 수익률 (Buy & Hold 계산용)
    bench_rets = df["close"].pct_change().fillna(0)
    
    metrics = compute_metrics(
        rets, n_trades, resolved_strategy, 
        str(df.index[0]), str(df.index[-1]), 
        trade_results=trade_results,
        benchmark_returns=bench_rets,
        costs=costs,
        long_returns=l_rets,
        short_returns=s_rets
    )

    # 5. UI용 거래 내역(Trades) 및 마커(Markers) 생성
    trades_payload = []
    markers = []
    pos = signal.shift(1).fillna(0)
    
    entry_price = 0.0
    
    for i in range(1, len(df)):
        current_pos = pos.iloc[i]
        prev_pos = pos.iloc[i-1]
        
        if current_pos != prev_pos:
            t_ms = int(df.index[i].timestamp())
            
            # [A] 이전 포지션 종료 (Exit)
            if prev_pos != 0:
                is_long_exit = prev_pos > 0
                exit_price = float(df["close"].iloc[i-1]) # 전 봉 종가에 종료
                
                # 수익 계산 (롱: 종가/진입가 - 1, 숏: 진입가/종가 - 1)
                if entry_price > 0:
                    profit_pct = (exit_price / entry_price - 1) if is_long_exit else (entry_price / exit_price - 1)
                else:
                    profit_pct = 0.0
                
                is_profit = profit_pct >= 0
                
                markers.append({
                    "time": t_ms, 
                    "position": "aboveBar" if is_long_exit else "belowBar",
                    "color": "#10b981" if is_profit else "#f43f5e", # TP: Emerald Green, SL: Rose Red
                    "shape": "circle", 
                    "text": "TP" if is_profit else "SL",
                })
                
                trades_payload.append({
                    "type": "LONG" if is_long_exit else "SHORT",
                    "time": df.index[i].isoformat(),
                    "exitReason": "TP" if is_profit else "SL",
                    "entry": entry_price,
                    "exit": exit_price,
                    "profitPct": f"{profit_pct*100:+.2f}%",
                    "posSize": 1.0
                })
            
            # [B] 새 포지션 진입 (Entry)
            if current_pos != 0:
                is_long_entry = current_pos > 0
                entry_price = float(df["close"].iloc[i-1]) # 신호 발생 시점의 가격으로 진입가 기록
                
                markers.append({
                    "time": t_ms, 
                    "position": "belowBar" if is_long_entry else "aboveBar",
                    "color": "#4ade80" if is_long_entry else "#fb7185",
                    "shape": "arrowUp" if is_long_entry else "arrowDown", 
                    "text": "L" if is_long_entry else "S",
                })

    # 6. 자산 곡선(Equity Curve) 생성
    cum_equity = (1 + rets).cumprod()
    equity_curve = []
    for t, val in cum_equity.items():
        equity_curve.append({
            "time": int(t.timestamp()),
            "value": float(val)
        })

    # 7. 결과 조립
    return {
        "success": True,
        "framework": "trinity-native-v2",
        "symbol": sanitize_symbol(symbol),
        "interval": interval,
        "strategy": strategy,
        "results": {
            "total_return": float(metrics.total_return * 100),
            "max_drawdown": abs(float(metrics.max_drawdown * 100)),
            "sharpe_ratio": float(metrics.sharpe),
            "sortino_ratio": float(metrics.sortino),
            "calmar_ratio": float(metrics.calmar),
            "win_rate": float(metrics.win_rate * 100) if metrics.n_trades > 0 else 0.0,
            "profit_factor": float(metrics.profit_factor),
            "total_trades": int(metrics.n_trades),
            "win_count": int(metrics.win_count),
            "loss_count": int(metrics.loss_count),
            "long_count": int(metrics.long_count),
            "short_count": int(metrics.short_count),
            "best_trade": float(metrics.best_trade * 100),
            "worst_trade": float(metrics.worst_trade * 100),
            "avg_profit": float(metrics.avg_profit * 100),
            "avg_loss": float(metrics.avg_loss * 100),
            "max_consecutive_wins": int(metrics.max_consecutive_wins),
            "max_consecutive_losses": int(metrics.max_consecutive_losses),
            "buy_hold": float(metrics.buy_hold_return * 100),
            "alpha": float((metrics.total_return - metrics.buy_hold_return) * 100),
            "total_fees": float(metrics.total_fees * 10000), 
            "long_return": float(metrics.long_return * 100),
            "long_pf": float(metrics.long_pf),
            "short_return": float(metrics.short_return * 100),
            "short_pf": float(metrics.short_pf),
            "expected_return": float(metrics.expected_return * 100),
            "total_pnl": float(metrics.total_return * 10000), 
        },
        "trades": trades_payload,
        "markers": markers,
        "candles": _candles_payload(df) if include_candles else [],
        "equity_curve": equity_curve
    }
