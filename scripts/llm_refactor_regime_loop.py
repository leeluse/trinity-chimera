#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import inspect
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.shared.llm.client import generate_chat_reply
from server.shared.db.supabase import SupabaseManager


REGIME_ORDER = ["Bull", "Bear", "Range", "HighVol"]
STRATEGIES_DIR = PROJECT_ROOT / "server" / "strategies"


def _load_regime_analysis_module():
    path = PROJECT_ROOT / "scripts" / "regime_performance_analysis.py"
    module_name = "regime_perf_analysis_module"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module from {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _normalize_strategy_token(token: str) -> str:
    s = str(token).strip()
    if s.endswith(".py"):
        s = s[:-3]
    return s


def _resolve_strategy_file(token: str) -> Path:
    norm = _normalize_strategy_token(token)

    direct = STRATEGIES_DIR / f"{norm}.py"
    if direct.exists():
        return direct

    lowered = norm.lower()
    for p in STRATEGIES_DIR.glob("*.py"):
        stem_l = p.stem.lower()
        if stem_l == lowered:
            return p
        if stem_l.startswith(lowered):
            return p
    raise FileNotFoundError(f"Strategy file not found for token='{token}'")


def _get_supabase_manager_or_none() -> Optional[SupabaseManager]:
    try:
        return SupabaseManager()
    except Exception as exc:
        print(f"[warn] Supabase unavailable: {exc}")
        return None


def _find_db_strategy_row(manager: SupabaseManager, token: str) -> Optional[Dict[str, Any]]:
    norm = _normalize_strategy_token(token)
    row = manager.get_strategy_by_key(strategy_key=norm)
    if row:
        return row

    rows = manager.list_strategies(limit=2000)
    lowered = norm.lower()
    for r in rows:
        params = r.get("params") or {}
        key = str(params.get("strategy_key") or "").strip() if isinstance(params, dict) else ""
        name = str(r.get("name") or "").strip()
        if key and (key.lower() == lowered or key.lower().startswith(lowered)):
            return r
        if name and (name.lower() == lowered or name.lower().startswith(lowered)):
            return r

        # normalize token style: Bull_01 ~= Bull Strategy 01
        normish = re.sub(r"[^a-z0-9]+", "", lowered)
        keyish = re.sub(r"[^a-z0-9]+", "", key.lower())
        nameish = re.sub(r"[^a-z0-9]+", "", name.lower())
        if normish and (normish == keyish or normish == nameish):
            return r
    return None


def _extract_strategy_key_from_row(row: Dict[str, Any]) -> str:
    params = row.get("params") or {}
    name = str(row.get("name") or "").strip()
    if name:
        return name
    if isinstance(params, dict):
        key = str(params.get("strategy_key") or "").strip()
        if key:
            return key
    return f"db_strategy_{row.get('id', 'unknown')}"


def _safe_id(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", str(text).strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return s or f"strategy_{uuid4().hex[:8]}"


def _insert_db_strategy_revision(
    manager: SupabaseManager,
    base_row: Dict[str, Any],
    strategy_key: str,
    code: str,
    rationale: str,
) -> Optional[str]:
    try:
        params = base_row.get("params") or {}
        if not isinstance(params, dict):
            params = {}
        params = dict(params)
        params["strategy_key"] = strategy_key

        agent_id = base_row.get("agent_id") or manager.ensure_system_agent()
        if not agent_id:
            return None
        next_version = manager.get_next_strategy_version(str(agent_id))
        payload = {
            "agent_id": str(agent_id),
            "version": int(next_version),
            "code": code,
            "name": base_row.get("name") or strategy_key,
            "params": params,
            "rationale": rationale,
            "source": base_row.get("source") or "chat",
        }
        res = manager.client.table("strategies").insert(payload, returning="representation").execute()
        rows = res.data or []
        if not rows:
            return None
        return str(rows[0].get("id"))
    except Exception as exc:
        print(f"[warn] Failed to insert DB strategy revision for {strategy_key}: {exc}")
        return None


def _resolve_strategy_specs(
    manager: Optional[SupabaseManager],
    strategy_tokens: List[str],
    source_mode: str,
) -> List[Dict[str, Any]]:
    specs: List[Dict[str, Any]] = []
    for token in strategy_tokens:
        norm = _normalize_strategy_token(token)
        added = False

        if source_mode in {"db", "auto"} and manager is not None:
            row = _find_db_strategy_row(manager, norm)
            if row and row.get("code"):
                params = row.get("params") or {}
                db_key = str(params.get("strategy_key") or "").strip() if isinstance(params, dict) else ""
                display = _extract_strategy_key_from_row(row)
                specs.append(
                    {
                        "id": _safe_id(display),
                        "display_name": display,
                        "regime_hint": display or norm,
                        "db_key": db_key,
                        "source": "db",
                        "db_row": row,
                        "file_path": None,
                    }
                )
                added = True

        if not added and source_mode in {"file", "auto"}:
            try:
                p = _resolve_strategy_file(norm)
                specs.append(
                    {
                        "id": p.stem,
                        "display_name": p.name,
                        "regime_hint": p.stem,
                        "db_key": "",
                        "source": "file",
                        "db_row": None,
                        "file_path": p,
                    }
                )
                added = True
            except Exception:
                pass

        if not added:
            raise FileNotFoundError(f"Strategy '{token}' not found in source={source_mode}")

    return specs


def _extract_regime_prefix(strategy_stem: str) -> Optional[str]:
    for regime in REGIME_ORDER:
        if strategy_stem.startswith(regime):
            return regime
    return None


def _load_module_from_path(module_path: Path):
    module_name = f"llm_loop_mod_{module_path.stem}_{uuid4().hex[:8]}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_generate_signal_from_code(code: str, out_dir: Path, file_tag: str):
    module_path = out_dir / f"{file_tag}.py"
    module_path.write_text(code, encoding="utf-8")
    module = _load_module_from_path(module_path)
    fn = getattr(module, "generate_signal", None)
    if not callable(fn):
        raise RuntimeError("generate_signal(train_df, test_df) not found in candidate code")
    return fn, module_path


def _extract_code_block(text: str) -> str:
    body = str(text or "").strip()
    if not body:
        return ""

    fence = re.search(r"```python\s*(.*?)```", body, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    fence2 = re.search(r"```\s*(.*?)```", body, flags=re.DOTALL)
    if fence2:
        return fence2.group(1).strip()
    return body


def _static_no_lookahead_checks(code: str) -> Tuple[bool, List[str]]:
    issues: List[str] = []
    checks = [
        (r"\.shift\(\s*-\d+", "negative shift detected (future reference)"),
        (r"rolling\([^)]*center\s*=\s*True", "center=True rolling detected (future leakage risk)"),
        (r"\.iloc\[\s*i\s*\+\s*1\s*\]", "iloc[i+1] detected (future bar access)"),
        (r"\.loc\[[^\]]*\+\s*1[^\]]*\]", "loc with +1 offset detected"),
        (r"bfill\(", "bfill detected (can leak future value into current row)"),
    ]
    for pattern, message in checks:
        if re.search(pattern, code):
            issues.append(message)

    if "def generate_signal(" not in code:
        issues.append("missing required function signature: generate_signal")
    if "test_df" not in code:
        issues.append("candidate does not appear to use test_df")

    return (len(issues) == 0), issues


@dataclass
class LeakCheckResult:
    ok: bool
    reason: str
    changed_ratio_max: float


def _dynamic_no_lookahead_check(
    strategy_fn,
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    sample_points: Tuple[float, ...] = (0.3, 0.5, 0.7),
    tol: float = 0.0,
) -> LeakCheckResult:
    if len(test_df) < 100:
        return LeakCheckResult(ok=False, reason="test_df too short for leak check", changed_ratio_max=1.0)

    base = strategy_fn(train_df, test_df)
    base = pd.Series(base, index=test_df.index)
    base = pd.to_numeric(base, errors="coerce").fillna(0.0)

    max_changed = 0.0
    rng = np.random.default_rng(20260429)

    for frac in sample_points:
        cut = int(len(test_df) * frac)
        if cut < 30 or cut >= len(test_df) - 5:
            continue

        mutated = test_df.copy()
        tail = mutated.iloc[cut:].copy()
        if len(tail) < 5:
            continue

        noise = rng.normal(loc=0.0, scale=0.08, size=len(tail))
        shock = np.cumprod(1.0 + noise)
        shock = np.clip(shock, 0.5, 2.0)

        for col in ["open", "high", "low", "close"]:
            if col in tail.columns:
                tail[col] = pd.to_numeric(tail[col], errors="coerce") * shock
        if "high" in tail.columns and "low" in tail.columns and "open" in tail.columns and "close" in tail.columns:
            hi = tail[["open", "high", "low", "close"]].max(axis=1)
            lo = tail[["open", "high", "low", "close"]].min(axis=1)
            tail["high"] = hi
            tail["low"] = lo
        if "volume" in tail.columns:
            tail["volume"] = pd.to_numeric(tail["volume"], errors="coerce") * (1.0 + np.abs(noise))

        mutated.iloc[cut:] = tail

        changed = strategy_fn(train_df, mutated)
        changed = pd.Series(changed, index=test_df.index)
        changed = pd.to_numeric(changed, errors="coerce").fillna(0.0)

        compare_end = cut - 1
        if compare_end < 1:
            continue

        left = base.iloc[:compare_end]
        right = changed.iloc[:compare_end]
        diff = (left != right).astype(float)
        changed_ratio = float(diff.mean()) if len(diff) else 0.0
        max_changed = max(max_changed, changed_ratio)
        if changed_ratio > tol:
            return LeakCheckResult(
                ok=False,
                reason=f"future perturbation changed past signals (cut={cut}, changed={changed_ratio:.4f})",
                changed_ratio_max=max_changed,
            )

    return LeakCheckResult(ok=True, reason="pass", changed_ratio_max=max_changed)


def _score_target_metrics(target_regime: str, metrics: Dict[str, float], min_trades: int) -> float:
    pf = float(metrics.get("profit_factor", 0.0))
    sharpe = float(metrics.get("sharpe", 0.0))
    monthly = float(metrics.get("monthly_return", 0.0))
    total_ret = float(metrics.get("total_return", 0.0))
    mdd = float(metrics.get("mdd", 0.0))
    trades = int(metrics.get("trades", 0))
    win_rate = float(metrics.get("win_rate", 0.0))

    base = (
        min(3.0, max(0.0, pf)) * 34.0
        + np.tanh(sharpe / 3.0) * 16.0
        + np.tanh(monthly * 8.0) * 24.0
        + np.tanh(total_ret * 2.5) * 10.0
        + min(2.0, trades / max(1.0, float(min_trades))) * 12.0
        + max(0.0, min(1.0, win_rate)) * 4.0
    )

    drawdown_penalty = max(0.0, abs(min(0.0, mdd)) - 0.08) * 120.0
    score = base - drawdown_penalty

    if target_regime == "Range":
        if trades < min_trades:
            score -= 20.0
        if trades == 0:
            score -= 60.0
    return float(score)


def _is_weak(target_regime: str, metrics: Dict[str, float], min_trades: int) -> bool:
    pf = float(metrics.get("profit_factor", 0.0))
    trades = int(metrics.get("trades", 0))
    monthly = float(metrics.get("monthly_return", 0.0))

    if target_regime == "Bull":
        return pf < 1.0 or monthly <= 0.0 or trades < min_trades
    if target_regime == "Range":
        return trades == 0 or pf < 1.0 or trades < min_trades
    return pf < 1.0 or trades < min_trades


def _build_refactor_prompt(
    strategy_file_name: str,
    target_regime: str,
    current_metrics: Dict[str, float],
    current_code: str,
    min_trades: int,
    code_chars_cap: int,
) -> str:
    compact_code = _compact_code_for_prompt(current_code, code_chars_cap)
    return f"""
You are refactoring a quantitative trading strategy Python file.

Target file: {strategy_file_name}
Target regime focus: {target_regime}

Current OOS metrics on target regime:
{json.dumps(current_metrics, indent=2)}

Goal:
1) Improve target-regime Profit Factor and monthly_return.
2) Keep drawdown controlled.
3) Ensure at least {min_trades} trades on target-regime OOS slices.

STRICT ANTI-LEAKAGE RULES (must follow):
- Never reference future bars.
- NEVER use shift(-N).
- NEVER use rolling(..., center=True).
- NEVER use iloc[i+1] or any forward index reference.
- Do not use bfill on indicator series.
- Any signal at time t must be computed only from <= t data.
- Keep function signature exactly:
  def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series

Implementation constraints:
- Use only numpy and pandas.
- Keep returned index aligned to test_df.index.
- Return integer-like signal values in [-1, 0, 1].
- Keep runtime vectorized/efficient for multi-year 15m data.

Output format:
- Return ONLY executable Python code.
- No markdown.
- Include imports and full function content.

Current code to refactor:
{compact_code}
""".strip()


def _compact_code_for_prompt(current_code: str, code_chars_cap: int) -> str:
    """
    Keep prompt latency stable by bounding oversized source blobs.
    Strategy DB entries can be very long; sending full text often causes LLM timeout.
    """
    text = str(current_code or "")
    cap = max(4000, int(code_chars_cap or 0))
    if len(text) <= cap:
        return text

    lines = text.splitlines()
    pruned: List[str] = []
    for ln in lines:
        stripped = ln.strip()
        if stripped.startswith("#"):
            continue
        if not stripped and pruned and not pruned[-1].strip():
            continue
        pruned.append(ln)
    compact = "\n".join(pruned).strip()
    if len(compact) <= cap:
        return compact

    head = int(cap * 0.62)
    tail = cap - head - 120
    if tail < 800:
        tail = 800
        head = cap - tail - 120
    return (
        compact[:head]
        + "\n\n# ... code truncated for prompt size budget ...\n\n"
        + compact[-tail:]
    )


def _candidate_notes(
    label: str,
    target_regime: str,
    score: float,
    metrics: Dict[str, float],
    leak: LeakCheckResult,
) -> str:
    return (
        f"[{label}] regime={target_regime} score={score:.3f} "
        f"PF={metrics.get('profit_factor', 0):.3f} "
        f"monthly={metrics.get('monthly_return', 0):+.3%} "
        f"MDD={metrics.get('mdd', 0):.3%} "
        f"trades={int(metrics.get('trades', 0))} "
        f"leak={leak.ok} changed={leak.changed_ratio_max:.4f}"
    )


def _apply_mutation_rules(code: str, rules: List[Tuple[str, str]]) -> Tuple[str, int]:
    out = str(code or "")
    changed = 0
    for pattern, repl in rules:
        out, count = re.subn(pattern, repl, out)
        changed += int(count)
    return out, changed


def _deterministic_mutation_candidates(
    code: str,
    target_regime: str,
    max_candidates: int,
) -> List[Dict[str, Any]]:
    if max_candidates <= 0:
        return []

    trend_light = [
        (r"(confirm_score\s*>=\s*)2\b", r"\g<1>1"),
        (r"(\*\s*)1\.20\b", r"\g<1>1.10"),
        (r"(\*\s*)1\.15\b", r"\g<1>1.08"),
        (r"(>=\s*)0\.15\b", r"\g<1>0.10"),
        (r"(<=\s*)0\.35\b", r"\g<1>0.45"),
        (r"(adx\w*\s*>=\s*)18\b", r"\g<1>16"),
        (r"(WARMUP\s*=\s*)400\b", r"\g<1>300"),
    ]
    trend_deep = [
        (r"(confirm_score\s*>=\s*)2\b", r"\g<1>1"),
        (r"(\*\s*)1\.20\b", r"\g<1>1.05"),
        (r"(\*\s*)1\.15\b", r"\g<1>1.05"),
        (r"(\*\s*)1\.10\b", r"\g<1>1.03"),
        (r"(>=\s*)0\.15\b", r"\g<1>0.05"),
        (r"(>=\s*)0\.10\b", r"\g<1>0.05"),
        (r"(<=\s*)0\.35\b", r"\g<1>0.55"),
        (r"(adx\w*\s*>=\s*)18\b", r"\g<1>14"),
        (r"(shift\(\s*)10(\s*\))", r"\g<1>5\g<2>"),
        (r"(WARMUP\s*=\s*)400\b", r"\g<1>240"),
    ]
    range_light = [
        (r"(adx\w*\s*<\s*)22\b", r"\g<1>26"),
        (r"(rsi\w*\s*<\s*)30\b", r"\g<1>35"),
        (r"(rsi\w*\s*>\s*)70\b", r"\g<1>65"),
        (r"(rsi\w*\s*>\s*)55\b", r"\g<1>52"),
        (r"(rsi\w*\s*<\s*)45\b", r"\g<1>48"),
        (r"(WARMUP\s*=\s*)400\b", r"\g<1>300"),
    ]
    range_deep = [
        (r"(adx\w*\s*<\s*)22\b", r"\g<1>30"),
        (r"(rsi\w*\s*<\s*)30\b", r"\g<1>40"),
        (r"(rsi\w*\s*>\s*)70\b", r"\g<1>60"),
        (r"(rsi\w*\s*>\s*)55\b", r"\g<1>50"),
        (r"(rsi\w*\s*<\s*)45\b", r"\g<1>50"),
        (r"(\*\s*)0\.3\b", r"\g<1>0.5"),
        (r"(WARMUP\s*=\s*)400\b", r"\g<1>240"),
    ]
    risk_tight = [
        (r"(\*\s*)0\.965\b", r"\g<1>0.975"),
        (r"(\*\s*)0\.955\b", r"\g<1>0.970"),
        (r"(\*\s*)3\.8\b", r"\g<1>2.8"),
        (r"(\*\s*)4\.5\b", r"\g<1>3.2"),
    ]
    risk_patient = [
        (r"(\*\s*)0\.965\b", r"\g<1>0.955"),
        (r"(\*\s*)0\.975\b", r"\g<1>0.965"),
        (r"(\*\s*)3\.8\b", r"\g<1>4.4"),
        (r"(\*\s*)2\.8\b", r"\g<1>3.5"),
    ]

    if target_regime == "Range":
        profiles = [
            ("range_light", range_light),
            ("range_deep", range_deep),
            ("range_light_risk_tight", range_light + risk_tight),
            ("range_deep_risk_patient", range_deep + risk_patient),
            ("trend_light", trend_light),
        ]
    else:
        profiles = [
            ("trend_light", trend_light),
            ("trend_deep", trend_deep),
            ("trend_light_risk_tight", trend_light + risk_tight),
            ("trend_deep_risk_patient", trend_deep + risk_patient),
            ("range_light", range_light),
        ]

    candidates: List[Dict[str, Any]] = []
    seen = {hashlib.sha1(str(code or "").encode("utf-8")).hexdigest()}
    for label, rules in profiles:
        mutated, changed = _apply_mutation_rules(code, rules)
        if changed <= 0 or mutated == code:
            continue
        digest = hashlib.sha1(mutated.encode("utf-8")).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        candidates.append(
            {
                "label": label,
                "code": mutated,
                "changed_rules": int(changed),
                "code_sha1": digest,
            }
        )
        if len(candidates) >= max_candidates:
            break
    return candidates


def _extract_regime_segments_local(
    df: pd.DataFrame,
    regime_series: pd.Series,
    target_regime: str,
    min_bars: int = 120,
    max_gap_bars: int = 20,
) -> List[pd.DataFrame]:
    mask = (regime_series.reindex(df.index).ffill().fillna("Range") == target_regime)
    raw_blocks: List[Tuple[int, int]] = []
    in_block = False
    start_idx = 0
    for i in range(len(df)):
        if bool(mask.iloc[i]) and not in_block:
            in_block = True
            start_idx = i
        elif (not bool(mask.iloc[i])) and in_block:
            in_block = False
            raw_blocks.append((start_idx, i))
    if in_block:
        raw_blocks.append((start_idx, len(df)))
    if not raw_blocks:
        return []

    merged: List[Tuple[int, int]] = []
    curr_s, curr_e = raw_blocks[0]
    for next_s, next_e in raw_blocks[1:]:
        if next_s - curr_e <= max_gap_bars:
            curr_e = next_e
        else:
            merged.append((curr_s, curr_e))
            curr_s, curr_e = next_s, next_e
    merged.append((curr_s, curr_e))

    out: List[pd.DataFrame] = []
    for s, e in merged:
        if e - s >= min_bars:
            out.append(df.iloc[s:e])
    return out


def _select_micro_segments(
    segments: List[pd.DataFrame],
    max_segments: int,
    max_bars: int,
) -> List[pd.DataFrame]:
    selected: List[pd.DataFrame] = []
    for seg in sorted(segments, key=len, reverse=True):
        if len(selected) >= max(1, int(max_segments)):
            break
        work = seg
        if len(work) > max_bars:
            work = work.iloc[-max_bars:]
        if len(work) >= 120:
            selected.append(work)
    return selected


def _report_from_target_metrics(
    regime_mod,
    strategy_name: str,
    target_regime: str,
    metrics: Dict[str, float],
    bars_per_day: int,
    segment_count: int,
) -> Dict[str, Any]:
    metrics_builder = getattr(regime_mod, "_metrics_from_returns", None)
    if callable(metrics_builder):
        empty = metrics_builder(pd.Series(dtype=float), [], [], 0.0, bars_per_day)
    else:
        empty = {
            "total_return": 0.0,
            "monthly_return": 0.0,
            "profit_factor": 0.0,
            "mdd": 0.0,
            "sharpe": 0.0,
            "max_consecutive_losses": 0,
            "trades": 0,
            "exposure_ratio": 0.0,
            "avg_hold_bars": 0.0,
            "avg_hold_hours": 0.0,
            "win_rate": 0.0,
        }
    by_regime = {regime: dict(empty) for regime in REGIME_ORDER}
    by_regime[target_regime] = metrics
    diagnosis_fn = getattr(regime_mod, "_regime_diagnosis", None)
    diagnosis = diagnosis_fn(by_regime) if callable(diagnosis_fn) else []
    return {
        "strategy": strategy_name,
        "oos_mode": "regime_sliced_micro",
        "target_regime": target_regime,
        "segment_count": int(segment_count),
        "overall": metrics,
        "by_regime": by_regime,
        "diagnosis": diagnosis,
    }


def _analyze_strategy_by_regime_compat(regime_mod, **kwargs) -> Dict[str, Any]:
    analyze_fn = getattr(regime_mod, "analyze_strategy_by_regime", None)
    if not callable(analyze_fn):
        raise RuntimeError("regime_performance_analysis.analyze_strategy_by_regime not found")
    sig = inspect.signature(analyze_fn)
    filtered = {k: v for k, v in kwargs.items() if k in sig.parameters}
    return analyze_fn(**filtered)


def _evaluate_segments_for_target(
    regime_mod,
    strategy_name: str,
    strategy_fn,
    segments: List[pd.DataFrame],
    target_regime: str,
    bars_per_day: int,
    leverage: float,
    oos_ratio: float,
    fee_rate: float,
    slippage: float,
    funding_rate: float,
) -> Dict[str, Any]:
    segmented_eval = getattr(regime_mod, "_evaluate_segmented_oos_for_regime", None)
    if callable(segmented_eval):
        eval_out = segmented_eval(
            strategy_name=strategy_name,
            strategy_fn=strategy_fn,
            segments=segments,
            regime_label=target_regime,
            bars_per_day=bars_per_day,
            leverage=leverage,
            oos_ratio=oos_ratio,
            fee_rate=fee_rate,
            slippage=slippage,
            funding_rate=funding_rate,
        )
        return _report_from_target_metrics(
            regime_mod=regime_mod,
            strategy_name=strategy_name,
            target_regime=target_regime,
            metrics=dict(eval_out["metrics"]),
            bars_per_day=bars_per_day,
            segment_count=len(segments),
        )

    if not segments:
        return _report_from_target_metrics(
            regime_mod=regime_mod,
            strategy_name=strategy_name,
            target_regime=target_regime,
            metrics={},
            bars_per_day=bars_per_day,
            segment_count=0,
        )

    df_seg = pd.concat(segments).sort_index()
    df_seg = df_seg[~df_seg.index.duplicated(keep="last")]
    regime_seg = pd.Series(target_regime, index=df_seg.index)
    rep = _analyze_strategy_by_regime_compat(
        regime_mod,
        strategy_name=strategy_name,
        strategy_fn=strategy_fn,
        df=df_seg,
        regime_series=regime_seg,
        bars_per_day=bars_per_day,
        leverage=leverage,
        oos_ratio=oos_ratio,
        segment_min_bars=120,
        segment_max_gap_bars=20,
        fee_rate=fee_rate,
        slippage=slippage,
        funding_rate=funding_rate,
    )
    metrics = dict((rep.get("by_regime") or {}).get(target_regime, {}))
    return _report_from_target_metrics(
        regime_mod=regime_mod,
        strategy_name=strategy_name,
        target_regime=target_regime,
        metrics=metrics,
        bars_per_day=bars_per_day,
        segment_count=len(segments),
    )


def _utc_now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _refactor_timeout_seconds() -> float:
    try:
        raw = float(os.getenv("LLM_REFACTOR_TIMEOUT_SECONDS", "20"))
    except Exception:
        raw = 20.0
    return max(10.0, min(raw, 300.0))


def _refactor_fallback_models() -> List[str]:
    raw = (os.getenv("LLM_REFACTOR_FALLBACK_MODELS") or "deepseek-v3.1-terminus").strip()
    models: List[str] = []
    for item in raw.split(","):
        m = item.strip()
        if m and m not in models:
            models.append(m)
    return models


def _looks_like_unavailable_response(content: str) -> bool:
    text = str(content or "").strip().lower()
    if not text:
        return True
    markers = [
        "현재 llm 모델과 연결할 수 없습니다",
        "llm 연결이 원활하지 않습니다",
        "service status",
        "connection error",
        "[llm 연결 오류",
        "로컬 ollama 연결 오류",
    ]
    return any(m in text for m in markers)


async def _call_llm_for_code(prompt: str, model: Optional[str], temperature: float, max_tokens: int) -> str:
    primary_model = (model or "").strip() or None
    candidates: List[Optional[str]] = []
    if primary_model:
        candidates.append(primary_model)
    for fb in _refactor_fallback_models():
        if fb and fb not in candidates:
            candidates.append(fb)
    if not candidates:
        candidates = [None]

    timeout_sec = _refactor_timeout_seconds()
    last_reason = "unknown"

    prev_ollama_fallback = os.getenv("LLM_ENABLE_OLLAMA_FALLBACK")
    os.environ["LLM_ENABLE_OLLAMA_FALLBACK"] = "0"
    try:
        for idx, candidate in enumerate(candidates):
            attempt_tokens = int(max_tokens) if idx == 0 else max(800, min(int(max_tokens), 2200))
            attempt_timeout = timeout_sec if idx == 0 else min(timeout_sec, 45.0)
            try:
                reply = await generate_chat_reply(
                    user_message=prompt,
                    context={},
                    model=candidate,
                    temperature=temperature,
                    timeout_sec=attempt_timeout,
                    max_tokens=attempt_tokens,
                    custom_system_prompt=(
                        "You are a strict Python quant strategy refactoring assistant. "
                        "Output only code. Follow anti-lookahead rules exactly."
                    ),
                )
                content = str(reply.get("content", "") or "")
                if _looks_like_unavailable_response(content):
                    err_text = str(reply.get("error", "") or "").strip()
                    provider = str(reply.get("provider", "") or "").strip()
                    if err_text:
                        last_reason = f"{provider or 'llm_error'} model={candidate or 'default'}: {err_text}"
                    else:
                        last_reason = f"unavailable response model={candidate or 'default'}"
                    continue
                return content
            except Exception as exc:
                last_reason = f"exception model={candidate or 'default'}: {exc}"
                continue
    finally:
        if prev_ollama_fallback is None:
            os.environ.pop("LLM_ENABLE_OLLAMA_FALLBACK", None)
        else:
            os.environ["LLM_ENABLE_OLLAMA_FALLBACK"] = prev_ollama_fallback

    raise RuntimeError(f"LLM unavailable after retries: {last_reason}")


def _safe_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in metrics.items():
        if isinstance(v, (np.floating, float)):
            out[k] = float(v)
        elif isinstance(v, (np.integer, int)):
            out[k] = int(v)
        else:
            out[k] = v
    return out


def _default_ohlcv_cache(symbol: str, timeframe: str, start: str, end: str) -> Path:
    return PROJECT_ROOT / "tmp" / "cache" / "ohlcv" / f"{symbol}_{timeframe}_{start}_{end}.parquet"


def _load_market_df_from_cache_local(cache_path: str, start_date: str, end_date: str) -> pd.DataFrame:
    df = pd.read_parquet(cache_path)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp")
    else:
        df.index = pd.to_datetime(df.index, utc=True)
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    df.columns = [str(c).lower() for c in df.columns]
    start_ts = pd.Timestamp(start_date, tz="UTC")
    end_ts = pd.Timestamp(end_date, tz="UTC") + pd.Timedelta(days=1)
    df = df.loc[start_ts:end_ts]
    if df.empty:
        raise RuntimeError(f"No data in cache for {start_date} ~ {end_date}")
    return df


def _read_regime_timeframe_from_stats(stats_path: Path) -> Optional[str]:
    if not stats_path.exists():
        return None
    try:
        payload = json.loads(stats_path.read_text(encoding="utf-8"))
        tf = str(payload.get("timeframe", "")).strip().lower()
        return tf or None
    except Exception:
        return None


def _find_latest_regime_labels_by_timeframe_local(preferred_timeframe: str) -> Optional[Path]:
    root = PROJECT_ROOT / "tmp" / "regime_runs"
    if not root.exists():
        return None
    candidates = list(root.glob("*/regime_labels.parquet"))
    if not candidates:
        return None

    preferred: List[Path] = []
    fallback: List[Path] = []
    pref_tf = str(preferred_timeframe or "").strip().lower()
    for p in candidates:
        tf = _read_regime_timeframe_from_stats(p.parent / "regime_stats.json")
        if pref_tf and tf == pref_tf:
            preferred.append(p)
        else:
            fallback.append(p)
    pool = preferred if preferred else fallback
    if not pool:
        return None
    return max(pool, key=lambda path: path.stat().st_mtime)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LLM loop refactor for weak Bull_01 / no-trade Range_01 with strict no-lookahead checks"
    )
    parser.add_argument(
        "--strategies",
        default="Bull_01_EMA_ADX_RSI_Pullback_NoLeakage,Range_01_RSI_MeanReversion_LongShort_NoLeakage",
        help="Comma-separated strategy file stems (with or without .py)",
    )
    parser.add_argument(
        "--source",
        default="auto",
        choices=["auto", "db", "file"],
        help="Strategy loading source priority (default: auto=DB first, then file)",
    )
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--timeframe", default="15m")
    parser.add_argument("--regime-timeframe", default="1h")
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument("--end", default="2026-01-31")
    parser.add_argument("--regime-labels", default="", help="Path to regime_labels.parquet (optional)")
    parser.add_argument("--ohlcv-cache", default="", help="Path to OHLCV parquet cache (optional)")
    parser.add_argument("--oos-ratio", type=float, default=0.4)
    parser.add_argument("--segment-min-bars", type=int, default=240)
    parser.add_argument("--segment-max-gap-bars", type=int, default=20)
    parser.add_argument("--min-trades", type=int, default=20)
    parser.add_argument("--leverage", type=float, default=1.0)
    parser.add_argument("--fee-rate", type=float, default=0.001)
    parser.add_argument("--slippage", type=float, default=0.0005)
    parser.add_argument("--funding-rate", type=float, default=0.0001)
    parser.add_argument("--iterations", type=int, default=6)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-tokens", type=int, default=1200)
    parser.add_argument("--mutation-candidates", type=int, default=12)
    parser.add_argument("--micro-segments", type=int, default=3)
    parser.add_argument("--micro-max-bars", type=int, default=5000)
    parser.add_argument("--full-candidates", type=int, default=2)
    parser.add_argument("--micro-min-delta", type=float, default=0.10)
    parser.add_argument(
        "--prompt-code-max-chars",
        type=int,
        default=6000,
        help="Max source chars injected into LLM refactor prompt",
    )
    parser.add_argument("--model", default="", help="Optional model override")
    parser.add_argument(
        "--only-weak",
        dest="only_weak",
        action="store_true",
        help="Refactor only weak strategies under current thresholds",
    )
    parser.add_argument(
        "--all-strategies",
        dest="only_weak",
        action="store_false",
        help="Process all target strategies (default)",
    )
    parser.set_defaults(only_weak=False)
    parser.add_argument("--apply-best", action="store_true", help="Overwrite strategy file if improved")
    parser.add_argument("--apply-best-db", action="store_true", help="Insert improved strategy as new DB revision")
    parser.add_argument("--out-dir", default="tmp/llm_regime_loop")
    args = parser.parse_args()

    regime_mod = _load_regime_analysis_module()

    run_root = PROJECT_ROOT / args.out_dir / _utc_now_tag()
    run_root.mkdir(parents=True, exist_ok=True)

    strategies_raw = [s.strip() for s in str(args.strategies).split(",") if s.strip()]
    manager = _get_supabase_manager_or_none() if (args.source in {"auto", "db"} or args.apply_best_db) else None
    strategy_specs = _resolve_strategy_specs(manager, strategies_raw, source_mode=str(args.source))
    print(f"[info] run_dir={run_root}")
    print("[info] strategies=" + ", ".join(f"{s['id']}[{s['source']}]" for s in strategy_specs))

    ohlcv_cache = Path(args.ohlcv_cache) if args.ohlcv_cache else _default_ohlcv_cache(
        args.symbol, args.timeframe, args.start, args.end
    )

    if ohlcv_cache.exists():
        cache_loader = getattr(regime_mod, "_load_market_df_from_cache", None)
        if callable(cache_loader):
            df = cache_loader(str(ohlcv_cache), args.start, args.end)
        else:
            df = _load_market_df_from_cache_local(str(ohlcv_cache), args.start, args.end)
        print(f"[data] loaded cache: {ohlcv_cache} bars={len(df)}")
    else:
        df = regime_mod._load_market_df(args.symbol, args.timeframe, args.start, args.end)
        print(f"[data] loaded provider bars={len(df)}")

    if args.regime_labels:
        regime_path = Path(args.regime_labels)
    else:
        preferred_tf = str(args.regime_timeframe).strip().lower()
        tf_finder = getattr(regime_mod, "_find_latest_regime_labels_by_timeframe", None)
        if callable(tf_finder):
            regime_path = tf_finder(preferred_tf)
        else:
            regime_path = _find_latest_regime_labels_by_timeframe_local(preferred_tf)
            if regime_path is None:
                fallback_finder = getattr(regime_mod, "_find_latest_regime_labels", None)
                regime_path = fallback_finder() if callable(fallback_finder) else None
    if regime_path is None or not Path(regime_path).exists():
        raise RuntimeError("regime_labels.parquet not found. Run regime labeler first.")

    regime_df = pd.read_parquet(regime_path)
    if "timestamp" in regime_df.columns:
        regime_df["timestamp"] = pd.to_datetime(regime_df["timestamp"], utc=True)
        regime_df = regime_df.set_index("timestamp")
    else:
        regime_df.index = pd.to_datetime(regime_df.index, utc=True)
    regime_df = regime_df.sort_index()
    regime_series = regime_df["regime"].reindex(df.index).ffill().bfill().fillna("Range")
    print(f"[regime] labels={regime_path}")

    bars_per_day = regime_mod.TF_BARS_PER_DAY.get(args.timeframe, 96)
    run_summary: Dict[str, Any] = {
        "meta": {
            "time_utc": datetime.now(timezone.utc).isoformat(),
            "symbol": args.symbol,
            "timeframe": args.timeframe,
            "regime_timeframe": args.regime_timeframe,
            "start": args.start,
            "end": args.end,
            "bars": int(len(df)),
            "iterations": int(args.iterations),
            "oos_ratio": float(args.oos_ratio),
            "segment_min_bars": int(args.segment_min_bars),
            "segment_max_gap_bars": int(args.segment_max_gap_bars),
            "min_trades": int(args.min_trades),
            "fee_rate": float(args.fee_rate),
            "slippage": float(args.slippage),
            "funding_rate": float(args.funding_rate),
            "regime_labels_path": str(regime_path),
            "ohlcv_cache_path": str(ohlcv_cache) if ohlcv_cache else "",
            "prompt_code_max_chars": int(args.prompt_code_max_chars),
            "mutation_candidates": int(args.mutation_candidates),
            "micro_segments": int(args.micro_segments),
            "micro_max_bars": int(args.micro_max_bars),
            "full_candidates": int(args.full_candidates),
            "micro_min_delta": float(args.micro_min_delta),
        },
        "strategies": [],
    }

    print(
        "[llm] timeout_sec="
        f"{_refactor_timeout_seconds():.1f} models={','.join(_refactor_fallback_models())} "
        f"max_tokens={int(args.max_tokens)} prompt_code_max_chars={int(args.prompt_code_max_chars)}"
    )

    for spec in strategy_specs:
        strategy_stem = str(spec["id"])
        regime_hint = str(spec.get("regime_hint") or strategy_stem)
        analysis_strategy_name = regime_hint
        target_regime = _extract_regime_prefix(regime_hint)
        if target_regime not in {"Bull", "Range"}:
            print(f"[skip] {strategy_stem}: target regime is not Bull/Range")
            continue

        strategy_dir = run_root / strategy_stem
        strategy_dir.mkdir(parents=True, exist_ok=True)

        if spec["source"] == "db":
            db_row = spec.get("db_row") or {}
            base_code = str(db_row.get("code") or "")
            if not base_code.strip():
                print(f"[skip] {strategy_stem}: empty DB code")
                continue
        else:
            fp = spec.get("file_path")
            if fp is None:
                print(f"[skip] {strategy_stem}: missing file path")
                continue
            base_code = Path(fp).read_text(encoding="utf-8")
        (strategy_dir / "baseline.py").write_text(base_code, encoding="utf-8")

        base_fn, _ = _load_generate_signal_from_code(base_code, strategy_dir, "candidate_baseline")
        base_report = _analyze_strategy_by_regime_compat(
            regime_mod,
            strategy_name=analysis_strategy_name,
            strategy_fn=base_fn,
            df=df,
            regime_series=regime_series,
            bars_per_day=bars_per_day,
            leverage=float(args.leverage),
            oos_ratio=float(args.oos_ratio),
            segment_min_bars=int(args.segment_min_bars),
            segment_max_gap_bars=int(args.segment_max_gap_bars),
            fee_rate=float(args.fee_rate),
            slippage=float(args.slippage),
            funding_rate=float(args.funding_rate),
        )
        base_metrics = dict(base_report["by_regime"].get(target_regime, {}))
        base_score = _score_target_metrics(target_regime, base_metrics, min_trades=int(args.min_trades))
        weak_now = _is_weak(target_regime, base_metrics, min_trades=int(args.min_trades))
        print(f"[baseline] {strategy_stem} weak={weak_now} score={base_score:.3f} metrics={_safe_metrics(base_metrics)}")

        strategy_result: Dict[str, Any] = {
            "strategy": strategy_stem,
            "target_regime": target_regime,
            "baseline": {
                "score": float(base_score),
                "metrics": _safe_metrics(base_metrics),
                "weak": bool(weak_now),
            },
            "iterations": [],
        }

        if args.only_weak and not weak_now:
            print(f"[skip] {strategy_stem}: not weak under current threshold")
            strategy_result["best"] = strategy_result["baseline"]
            run_summary["strategies"].append(strategy_result)
            continue

        segment_extractor = getattr(regime_mod, "_extract_regime_segments", None)
        if callable(segment_extractor):
            segments = segment_extractor(
                df,
                regime_series,
                target_regime,
                min_bars=max(int(args.segment_min_bars), 120),
                max_gap_bars=int(args.segment_max_gap_bars),
            )
        else:
            segments = _extract_regime_segments_local(
                df,
                regime_series,
                target_regime,
                min_bars=max(int(args.segment_min_bars), 120),
                max_gap_bars=int(args.segment_max_gap_bars),
            )
        if not segments:
            print(f"[skip] {strategy_stem}: no regime segments available")
            strategy_result["best"] = strategy_result["baseline"]
            run_summary["strategies"].append(strategy_result)
            continue

        leak_seg = max(segments, key=len)
        leak_split = max(20, int(len(leak_seg) * (1.0 - float(args.oos_ratio))))
        leak_train = leak_seg.iloc[:leak_split]
        leak_test = leak_seg.iloc[leak_split:]
        if len(leak_test) < 60:
            leak_train = leak_seg.iloc[: max(20, int(len(leak_seg) * 0.6))]
            leak_test = leak_seg.iloc[max(20, int(len(leak_seg) * 0.6)) :]

        best_code = base_code
        best_score = base_score
        best_metrics = base_metrics
        best_report = base_report
        best_origin = "baseline"

        current_code = base_code
        micro_segments = _select_micro_segments(
            segments,
            max_segments=int(args.micro_segments),
            max_bars=int(args.micro_max_bars),
        )
        mutation_rows: List[Dict[str, Any]] = []
        mutation_improved = False
        base_micro_score: Optional[float] = None

        if micro_segments and int(args.mutation_candidates) > 0:
            try:
                base_micro_report = _evaluate_segments_for_target(
                    regime_mod=regime_mod,
                    strategy_name=analysis_strategy_name,
                    strategy_fn=base_fn,
                    segments=micro_segments,
                    target_regime=target_regime,
                    bars_per_day=bars_per_day,
                    leverage=float(args.leverage),
                    oos_ratio=float(args.oos_ratio),
                    fee_rate=float(args.fee_rate),
                    slippage=float(args.slippage),
                    funding_rate=float(args.funding_rate),
                )
                base_micro_metrics = dict(base_micro_report["by_regime"].get(target_regime, {}))
                base_micro_score = _score_target_metrics(
                    target_regime,
                    base_micro_metrics,
                    min_trades=int(args.min_trades),
                )
                strategy_result["micro_baseline"] = {
                    "score": float(base_micro_score),
                    "metrics": _safe_metrics(base_micro_metrics),
                    "segments": len(micro_segments),
                    "bars": int(sum(len(s) for s in micro_segments)),
                }
                print(
                    f"[mutate] {strategy_stem}: micro baseline "
                    f"score={base_micro_score:.3f} segments={len(micro_segments)}",
                    flush=True,
                )
            except Exception as exc:
                strategy_result["micro_baseline_error"] = str(exc)
                print(f"[mutate] {strategy_stem}: micro baseline failed: {exc}", flush=True)

            raw_mutations = _deterministic_mutation_candidates(
                current_code,
                target_regime=target_regime,
                max_candidates=int(args.mutation_candidates),
            )
            print(f"[mutate] {strategy_stem}: candidates={len(raw_mutations)}", flush=True)
            micro_candidates: List[Tuple[float, Dict[str, Any], Any, str]] = []

            for mi, mutation in enumerate(raw_mutations, start=1):
                label = str(mutation["label"])
                candidate_code = str(mutation["code"])
                row: Dict[str, Any] = {
                    "label": label,
                    "changed_rules": int(mutation.get("changed_rules", 0)),
                    "code_sha1": str(mutation.get("code_sha1", "")),
                    "accepted": False,
                }

                static_ok, static_issues = _static_no_lookahead_checks(candidate_code)
                row["static_ok"] = static_ok
                row["static_issues"] = static_issues
                if not static_ok:
                    row["error"] = "static lookahead check failed"
                    mutation_rows.append(row)
                    print(f"[mutate] {strategy_stem}: {label} rejected(static): {static_issues}", flush=True)
                    continue

                try:
                    candidate_fn, candidate_path = _load_generate_signal_from_code(
                        candidate_code, strategy_dir, f"candidate_mut_{mi:02d}_{_safe_id(label)}"
                    )
                except Exception as exc:
                    row["error"] = f"compile/load failed: {exc}"
                    mutation_rows.append(row)
                    print(f"[mutate] {strategy_stem}: {label} rejected(load): {exc}", flush=True)
                    continue

                try:
                    micro_report = _evaluate_segments_for_target(
                        regime_mod=regime_mod,
                        strategy_name=analysis_strategy_name,
                        strategy_fn=candidate_fn,
                        segments=micro_segments,
                        target_regime=target_regime,
                        bars_per_day=bars_per_day,
                        leverage=float(args.leverage),
                        oos_ratio=float(args.oos_ratio),
                        fee_rate=float(args.fee_rate),
                        slippage=float(args.slippage),
                        funding_rate=float(args.funding_rate),
                    )
                except Exception as exc:
                    row["error"] = f"micro evaluation failed: {exc}"
                    mutation_rows.append(row)
                    print(f"[mutate] {strategy_stem}: {label} rejected(micro): {exc}", flush=True)
                    continue

                micro_metrics = dict(micro_report["by_regime"].get(target_regime, {}))
                micro_score = _score_target_metrics(
                    target_regime,
                    micro_metrics,
                    min_trades=int(args.min_trades),
                )
                row["micro_score"] = float(micro_score)
                row["micro_metrics"] = _safe_metrics(micro_metrics)
                row["candidate_file"] = str(candidate_path)
                mutation_rows.append(row)
                micro_candidates.append((float(micro_score), row, candidate_fn, candidate_code))
                delta = micro_score - base_micro_score if base_micro_score is not None else 0.0
                print(
                    f"[mutate] {strategy_stem}: {label} micro_score={micro_score:.3f} "
                    f"delta={delta:+.3f}",
                    flush=True,
                )

            min_delta = float(args.micro_min_delta)
            full_queue = [
                item for item in micro_candidates
                if base_micro_score is None or item[0] >= base_micro_score + min_delta
            ]
            full_queue = sorted(full_queue, key=lambda item: item[0], reverse=True)[: max(0, int(args.full_candidates))]

            for micro_score, row, candidate_fn, candidate_code in full_queue:
                label = str(row.get("label") or "mutation")
                leak = _dynamic_no_lookahead_check(candidate_fn, leak_train, leak_test)
                row["leak_check"] = {
                    "ok": bool(leak.ok),
                    "reason": leak.reason,
                    "changed_ratio_max": float(leak.changed_ratio_max),
                }
                if not leak.ok:
                    row["error"] = f"dynamic lookahead check failed: {leak.reason}"
                    print(f"[mutate] {strategy_stem}: {label} rejected(leak): {leak.reason}", flush=True)
                    continue

                try:
                    report = _analyze_strategy_by_regime_compat(
                        regime_mod,
                        strategy_name=analysis_strategy_name,
                        strategy_fn=candidate_fn,
                        df=df,
                        regime_series=regime_series,
                        bars_per_day=bars_per_day,
                        leverage=float(args.leverage),
                        oos_ratio=float(args.oos_ratio),
                        segment_min_bars=int(args.segment_min_bars),
                        segment_max_gap_bars=int(args.segment_max_gap_bars),
                        fee_rate=float(args.fee_rate),
                        slippage=float(args.slippage),
                        funding_rate=float(args.funding_rate),
                    )
                except Exception as exc:
                    row["error"] = f"full evaluation failed: {exc}"
                    print(f"[mutate] {strategy_stem}: {label} rejected(full): {exc}", flush=True)
                    continue

                metrics = dict(report["by_regime"].get(target_regime, {}))
                score = _score_target_metrics(target_regime, metrics, min_trades=int(args.min_trades))
                improve = score > (best_score + 1e-9)
                row["full_score"] = float(score)
                row["full_metrics"] = _safe_metrics(metrics)
                row["accepted"] = bool(improve)
                print(
                    f"[mutate] {strategy_stem}: {label} full_score={score:.3f} "
                    f"accepted={improve}",
                    flush=True,
                )

                if improve:
                    best_score = score
                    best_metrics = metrics
                    best_report = report
                    best_code = candidate_code
                    current_code = candidate_code
                    best_origin = f"mutation:{label}"
                    mutation_improved = True
                    (strategy_dir / "best_so_far.py").write_text(best_code, encoding="utf-8")

        strategy_result["mutations"] = mutation_rows

        llm_iterations = int(args.iterations)
        if mutation_improved:
            strategy_result["llm_skipped_reason"] = "deterministic mutation improved full OOS"
            llm_iterations = 0
            print(f"[progress] {strategy_stem}: deterministic improvement found -> skip LLM", flush=True)

        print(f"[progress] {strategy_stem}: iterations={llm_iterations} start", flush=True)
        for i in range(1, llm_iterations + 1):
            print(f"[progress] {strategy_stem}: iter {i}/{llm_iterations} LLM request", flush=True)
            prompt = _build_refactor_prompt(
                strategy_file_name=str(spec.get("display_name") or strategy_stem),
                target_regime=target_regime,
                current_metrics=_safe_metrics(best_metrics),
                current_code=current_code,
                min_trades=int(args.min_trades),
                code_chars_cap=int(args.prompt_code_max_chars),
            )
            try:
                llm_raw = asyncio.run(
                    _call_llm_for_code(
                        prompt=prompt,
                        model=(args.model or None),
                        temperature=float(args.temperature),
                        max_tokens=int(args.max_tokens),
                    )
                )
            except Exception as exc:
                iter_row = {
                    "iter": i,
                    "accepted": False,
                    "error": f"llm call failed: {exc}",
                }
                strategy_result["iterations"].append(iter_row)
                print(f"[iter {i}] {strategy_stem} rejected(llm): {exc}")
                continue
            if not str(llm_raw or "").strip():
                iter_row = {
                    "iter": i,
                    "accepted": False,
                    "error": "empty llm response",
                }
                strategy_result["iterations"].append(iter_row)
                print(f"[iter {i}] {strategy_stem} rejected(llm): empty response")
                continue
            print(f"[progress] {strategy_stem}: iter {i}/{llm_iterations} LLM response received", flush=True)
            candidate_code = _extract_code_block(llm_raw)
            iter_row: Dict[str, Any] = {
                "iter": i,
                "accepted": False,
                "error": "",
            }

            static_ok, static_issues = _static_no_lookahead_checks(candidate_code)
            iter_row["static_ok"] = static_ok
            iter_row["static_issues"] = static_issues
            if not static_ok:
                iter_row["error"] = "static lookahead check failed"
                strategy_result["iterations"].append(iter_row)
                print(f"[iter {i}] {strategy_stem} rejected(static): {static_issues}")
                continue

            try:
                candidate_fn, candidate_path = _load_generate_signal_from_code(
                    candidate_code, strategy_dir, f"candidate_iter_{i:02d}"
                )
            except Exception as exc:
                iter_row["error"] = f"compile/load failed: {exc}"
                strategy_result["iterations"].append(iter_row)
                print(f"[iter {i}] {strategy_stem} rejected(load): {exc}")
                continue

            leak = _dynamic_no_lookahead_check(candidate_fn, leak_train, leak_test)
            iter_row["leak_check"] = {
                "ok": bool(leak.ok),
                "reason": leak.reason,
                "changed_ratio_max": float(leak.changed_ratio_max),
            }
            if not leak.ok:
                iter_row["error"] = f"dynamic lookahead check failed: {leak.reason}"
                strategy_result["iterations"].append(iter_row)
                print(f"[iter {i}] {strategy_stem} rejected(leak): {leak.reason}")
                continue

            try:
                report = _analyze_strategy_by_regime_compat(
                    regime_mod,
                    strategy_name=analysis_strategy_name,
                    strategy_fn=candidate_fn,
                    df=df,
                    regime_series=regime_series,
                    bars_per_day=bars_per_day,
                    leverage=float(args.leverage),
                    oos_ratio=float(args.oos_ratio),
                    segment_min_bars=int(args.segment_min_bars),
                    segment_max_gap_bars=int(args.segment_max_gap_bars),
                    fee_rate=float(args.fee_rate),
                    slippage=float(args.slippage),
                    funding_rate=float(args.funding_rate),
                )
            except Exception as exc:
                iter_row["error"] = f"evaluation failed: {exc}"
                strategy_result["iterations"].append(iter_row)
                print(f"[iter {i}] {strategy_stem} rejected(eval): {exc}")
                continue

            metrics = dict(report["by_regime"].get(target_regime, {}))
            score = _score_target_metrics(target_regime, metrics, min_trades=int(args.min_trades))

            iter_row["score"] = float(score)
            iter_row["metrics"] = _safe_metrics(metrics)
            iter_row["candidate_file"] = str(candidate_path)
            print(_candidate_notes(f"{strategy_stem} iter {i}", target_regime, score, metrics, leak))

            improve = score > (best_score + 1e-9)
            if improve:
                best_score = score
                best_metrics = metrics
                best_report = report
                best_code = candidate_code
                current_code = candidate_code
                best_origin = f"llm_iter_{i}"
                iter_row["accepted"] = True
                (strategy_dir / "best_so_far.py").write_text(best_code, encoding="utf-8")
            else:
                iter_row["accepted"] = False
                current_code = best_code

            strategy_result["iterations"].append(iter_row)
            print(
                f"[progress] {strategy_stem}: iter {i}/{llm_iterations} "
                f"score={score:.3f} accepted={iter_row['accepted']}",
                flush=True,
            )

        best_path = strategy_dir / "best.py"
        best_path.write_text(best_code, encoding="utf-8")
        (strategy_dir / "best_report.json").write_text(
            json.dumps(
                {
                    "strategy": strategy_stem,
                    "target_regime": target_regime,
                    "score": float(best_score),
                    "metrics": _safe_metrics(best_metrics),
                    "oos_report": best_report,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        improved = bool(best_score > base_score + 1e-9)
        if improved:
            if args.apply_best and spec["source"] == "file":
                fp = Path(spec["file_path"])
                fp.write_text(best_code, encoding="utf-8")
                print(f"[apply] updated file {fp}")
            if args.apply_best_db and manager is not None and spec["source"] == "db":
                db_row = spec.get("db_row") or {}
                db_key = str(spec.get("db_key") or "")
                strategy_id = _insert_db_strategy_revision(
                    manager=manager,
                    base_row=db_row,
                    strategy_key=db_key or strategy_stem,
                    code=best_code,
                    rationale=f"Regime loop improvement ({target_regime}, source={best_origin})",
                )
                if strategy_id:
                    print(f"[apply] inserted DB revision strategy_id={strategy_id}")
                else:
                    print(f"[warn] apply-best-db failed for {strategy_stem}")

        strategy_result["best"] = {
            "score": float(best_score),
            "metrics": _safe_metrics(best_metrics),
            "improved_vs_baseline": improved,
            "best_file": str(best_path),
            "source": spec["source"],
            "selection_source": best_origin,
        }
        print(
            f"[progress] {strategy_stem}: done improved={improved} best_score={best_score:.3f}",
            flush=True,
        )
        run_summary["strategies"].append(strategy_result)

    out_json = run_root / "summary.json"
    out_json.write_text(json.dumps(run_summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[done] summary={out_json}")


if __name__ == "__main__":
    main()
