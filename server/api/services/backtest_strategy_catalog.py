from __future__ import annotations

from typing import Any, Dict, List, Optional

from server.api.services.skill_backtest_runtime import list_skill_strategies


# Prompt-routing and presentation metadata are intentionally separated
# from the runtime executor so strategy selection logic can evolve independently.
STRATEGY_PRESETS: Dict[str, Dict[str, Any]] = {
    "donchian_breakout_atr": {
        "title": "Donchian Breakout ATR (Relaxed)",
        "description": "Donchian Channel breakout strategy with ATR-based risk controls.",
        "keywords": ["돈치안", "donchian", "돌파", "breakout", "atr"],
        "params": {
            "period": 15,
            "atr_period": 14,
            "range_bars": 5,
            "range_atr_mult": 6.0,
            "sl_atr_mult": 1.5,
            "tp_atr_mult": 3.0,
        },
        "features": [
            "돈치안 채널 돌파 진입",
            "ATR 기반 손절/익절",
            "횡보 구간 필터",
        ],
    },
    "optPredator": {
        "title": "MINARA V2",
        "description": "High-frequency momentum breakout strategy with adaptive ATR filters.",
        "keywords": ["minara", "predator", "momentum", "breakout", "돌파", "모멘텀"],
        "features": [
            "진동 구간 감지 및 돌파 필터링",
            "동적 그리드 기반 포지션 스케일링",
        ],
    },
    "optQuantum": {
        "title": "ARBITER V1",
        "description": "Mean-reversion engine focused on liquidity exhaustion and trend recovery.",
        "keywords": ["arbiter", "quantum", "mean", "reversion", "반전", "평균회귀"],
        "features": [
            "유동성 고갈 구간 포착",
            "델타 중립 기반 평균 복귀 로직",
        ],
    },
    "optWhale": {
        "title": "NIM-ALPHA",
        "description": "Macro trend tracker analyzing large-volume order flow and structural breakouts.",
        "keywords": ["nim", "alpha", "whale", "macro", "trend", "추세", "기관"],
        "features": [
            "대형 주문 흐름 추적",
            "시나리오 기반 추세 지속형 진입",
        ],
    },
    "optApexV2": {
        "title": "CHIMERA-β",
        "description": "Advanced multi-factor alpha engine with complex signal convolution.",
        "keywords": ["chimera", "apex", "alpha", "multifactor", "알파", "복합"],
        "features": [
            "다중 지표 컨볼루션 연산",
            "손익비 최적화 기반 자동 청산",
        ],
    },
    "rsi_reversal": {
        "keywords": ["rsi", "반전", "reversal"],
    },
    "ema_crossover": {
        "keywords": ["ema", "crossover", "교차"],
    },
    "macd": {
        "keywords": ["macd", "signal", "히스토그램"],
    },
    "breakout": {
        "keywords": ["breakout", "돌파", "채널"],
    },
}

PREFERRED_FALLBACK_ORDER = [
    "donchian_breakout_atr",
    "optPredator",
    "ema_crossover",
    "macd",
    "rsi_reversal",
    "breakout",
]


def _available_map() -> Dict[str, Dict[str, Any]]:
    return {item["key"]: item for item in list_skill_strategies()}


def list_strategy_keys() -> List[str]:
    return list(_available_map().keys())


def resolve_strategy_key(message: str, preferred_strategy: Optional[str] = None) -> str:
    available = _available_map()
    if not available:
        raise RuntimeError("No strategies available from skill runtime")

    if preferred_strategy and preferred_strategy in available:
        return preferred_strategy

    text = (message or "").lower()
    scored: Dict[str, int] = {}

    for key, preset in STRATEGY_PRESETS.items():
        if key not in available:
            continue
        keywords = [str(k).lower() for k in preset.get("keywords", [])]
        if not keywords:
            continue

        score = 0
        for kw in keywords:
            if kw and kw in text:
                score += 1
        if score > 0:
            scored[key] = score

    if scored:
        return sorted(scored.items(), key=lambda item: (-item[1], item[0]))[0][0]

    for key in PREFERRED_FALLBACK_ORDER:
        if key in available:
            return key

    return sorted(available.keys())[0]


def get_strategy_meta(strategy_key: str) -> Dict[str, Any]:
    available = _available_map()
    item = available.get(strategy_key, {})
    preset = STRATEGY_PRESETS.get(strategy_key, {})

    title = str(preset.get("title") or item.get("label") or strategy_key)
    description = str(preset.get("description") or item.get("description") or "")
    features = list(preset.get("features") or ([] if not description else [description]))

    return {
        "strategy_key": strategy_key,
        "title": title,
        "description": description,
        "features": features,
        "params": dict(preset.get("params") or {}),
        "native_key": item.get("native_key") or strategy_key,
        "class_name": item.get("class_name"),
    }
