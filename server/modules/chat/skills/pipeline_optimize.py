"""파라미터 최적화 파이프라인 (코드에서 파라미터 추출 → Grid Search → 최적값 선택)"""
import json
import logging
import re
from itertools import product
from typing import Any, AsyncGenerator, Dict, List

from server.shared.llm.client import stream_quick_reply
from server.modules.backtest.chat.chat_backtester import ChatBacktester
from server.modules.evolution.scoring import calculate_trinity_score
from server.modules.chat.skills._base import format_sse

logger = logging.getLogger(__name__)


def _scan_params_from_code(code: str) -> Dict[str, float]:
    """
    코드에서 `변수명 = 숫자` 패턴을 정적으로 스캔해 {이름: 현재값} 반환.
    LLM 추출 결과의 이름 검증 및 fallback에 사용.
    """
    found: Dict[str, float] = {}
    for m in re.finditer(r"^\s*([a-zA-Z_]\w*)\s*=\s*(\d+\.?\d*)\s*(?:#.*)?$", code, re.MULTILINE):
        name, val_str = m.group(1), m.group(2)
        v = float(val_str)
        found[name] = int(v) if v == int(v) else v
    return found


async def _extract_params_from_code(strategy_code: str) -> Dict[str, Any]:
    """
    LLM을 사용해 전략 코드에서 최적화 가능한 파라미터 추출.
    추출된 이름이 코드에 실제로 존재하지 않으면 제거한다.
    응답: {"params": [{"name": "...", "current": ..., "min": ..., "max": ..., "step": ...}]}
    """
    # 코드에 실제 존재하는 숫자 변수를 미리 스캔
    code_vars = _scan_params_from_code(strategy_code)

    prompt = f"""
    다음 전략 코드에서 최적화 가능한 수치 파라미터를 추출해라.
    최적화 대상: 이동평균 기간, 임계값, 손절/익절 비율, 룩백 기간, 모멘텀 기간, ATR 배수 등.

    ⚠️ 핵심 규칙:
    - "name" 필드는 반드시 코드에 실제로 존재하는 변수명 그대로 사용해라. 절대 만들어 내지 마라.
    - 고정된 수치 상수만 추출 (정수 또는 실수 모두 포함)
    - 너무 작은 값(1-2)은 제외
    - 최대 5개까지만 반환 (중요도 순)
    - current 값은 코드에 적힌 실제 값이어야 한다
    - min/max는 current 기준 ±50% 내외로 설정, step은 current의 약 10% 수준

    JSON 배열로만 응답해라. 다른 텍스트 금지:
    [
      {{"name": "변수명", "current": 현재값, "min": 최소값, "max": 최대값, "step": 간격}},
      ...
    ]

    코드:
    ```python
    {strategy_code}
    ```
    """

    response = ""
    async for chunk in stream_quick_reply(prompt):
        content = chunk.get("content", "")
        if content:
            response += content

    response = response.strip()

    # JSON 추출
    try:
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]

        params = json.loads(response)
        if not isinstance(params, list):
            params = []

        valid_params = []
        for p in params:
            if not all(k in p for k in ["name", "current", "min", "max", "step"]):
                continue
            try:
                for key in ("current", "min", "max", "step"):
                    v = float(p[key])
                    p[key] = int(v) if v == int(v) else v
                if p["step"] <= 0 or p["min"] > p["max"]:
                    continue
            except (TypeError, ValueError):
                continue

            # ── 이름 검증: 코드에 없으면 제거 ──────────────────────
            if p["name"] not in code_vars:
                logger.warning(f"[Optimize] LLM hallucinated param name '{p['name']}' — not found in code, skipping")
                continue

            # current 값도 코드의 실제 값으로 교정
            p["current"] = code_vars[p["name"]]
            valid_params.append(p)

        # LLM이 하나도 못 찾으면 코드 스캔 결과로 fallback
        if not valid_params and code_vars:
            valid_params = _fallback_params(code_vars)

        return {"params": valid_params}
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse params from LLM response: {response[:200]}")
        fallback = _fallback_params(code_vars) if code_vars else []
        return {"params": fallback}


def _fallback_params(code_vars: Dict[str, float]) -> List[Dict[str, Any]]:
    """
    LLM 실패 시 코드 스캔 결과에서 파라미터를 자동 선택 (값이 클수록 이동평균/기간류 우선).
    최대 3개, 값이 3 이상인 정수 변수만 선택.
    """
    candidates = [
        (name, val) for name, val in code_vars.items()
        if isinstance(val, int) and val >= 3
    ]
    # 이름에 len/period/window/lookback 등이 포함된 것 우선
    priority_keywords = ("len", "period", "window", "lookback", "span", "n_", "_n")
    priority = [c for c in candidates if any(k in c[0].lower() for k in priority_keywords)]
    rest = [c for c in candidates if c not in priority]
    selected = (priority + rest)[:3]

    result = []
    for name, val in selected:
        half = max(1, val // 2)
        step = max(1, val // 10)
        result.append({
            "name": name,
            "current": val,
            "min": max(2, val - half),
            "max": val + half,
            "step": step,
        })
    return result


def _float_range(min_v: float, max_v: float, step: float) -> List[float]:
    """float 간격의 파라미터 범위 생성."""
    values = []
    v = min_v
    while v <= max_v + 1e-9:
        values.append(round(v, 10))
        v = round(v + step, 10)
    return values


def _generate_param_grid(params: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    파라미터 목록에서 탐색할 조합 생성 (int/float 모두 지원).
    - 파라미터 3개 이하: 전체 조합 (최대 30개)
    - 4개 이상: 상위 2개만 (최대 20개)
    """
    if not params:
        return []

    target = params if len(params) <= 3 else params[:2]
    limit = 30 if len(params) <= 3 else 20

    ranges = []
    for p in target:
        values = _float_range(float(p["min"]), float(p["max"]), float(p["step"]))
        ranges.append([(p["name"], v) for v in values])

    combinations = []
    for combo in product(*ranges):
        combinations.append(dict(combo))

    return combinations[:limit]


def _apply_params_to_code(code: str, param_values: Dict[str, int]) -> str:
    """
    코드에 파라미터 값 적용 (정규식으로 변수 값 교체).
    """
    modified_code = code

    for param_name, param_value in param_values.items():
        # 변수명 = 숫자(정수 또는 소수) 형태 찾아서 교체
        pattern = rf"({re.escape(param_name)}\s*=\s*)(\d+\.?\d*)"
        replacement = rf"\g<1>{param_value}"
        modified_code = re.sub(pattern, replacement, modified_code)

    return modified_code


async def run_optimize_pipeline(
    message: str,
    context: Dict[str, Any],
    strategy_code: str,
    _: Dict[str, Any],
) -> AsyncGenerator[str, None]:
    """
    파라미터 최적화 파이프라인.
    Stage 1: 파라미터 추출
    Stage 2: Grid Search (백테스트 반복)
    Stage 3: 최적값 선택 + 요약
    """
    try:
        if not strategy_code:
            yield format_sse({
                "type": "error",
                "content": "❌ 최적화할 전략 코드가 없습니다. 먼저 전략을 생성해주세요."
            })
            return

        # ── Stage 1: 파라미터 추출 ──────────────────
        yield format_sse({"type": "stage", "stage": 1, "label": "🔍 최적화 가능한 파라미터 추출 중..."})

        param_result = await _extract_params_from_code(strategy_code)
        params = param_result.get("params", [])

        if not params:
            yield format_sse({"type": "analysis", "content": "⚠️ 코드에서 최적화할 수치 파라미터를 찾지 못했습니다."})
            yield format_sse({"type": "done"})
            return

        param_summary = "\n".join(
            f"  • `{p['name']}` = {p['current']}  →  [{p['min']} ~ {p['max']}, 간격 {p['step']}]"
            for p in params
        )
        yield format_sse({"type": "analysis", "content": f"**추출된 최적화 파라미터:**\n{param_summary}"})

        # ── Stage 2: Grid Search ──────────────────────
        param_grid = _generate_param_grid(params)
        if not param_grid:
            yield format_sse({"type": "analysis", "content": "❌ 탐색할 파라미터 조합이 없습니다."})
            yield format_sse({"type": "done"})
            return

        yield format_sse({"type": "stage", "stage": 2, "label": f"⚙️ 파라미터 탐색 중... (0/{len(param_grid)})"})

        backtester = ChatBacktester()
        results = []

        for idx, param_values in enumerate(param_grid):
            modified_code = _apply_params_to_code(strategy_code, param_values)
            try:
                bt_res = await backtester.run(modified_code, message, context)
                if not bt_res.get("success"):
                    raise Exception(bt_res.get("error", "Unknown error"))

                bt_metrics = bt_res.get("metrics", {})
                # bt_metrics의 total_return/max_drawdown은 퍼센트 단위 (예: -281.38, 27.04)
                metrics = {
                    "total_return": bt_metrics.get("total_return", 0),
                    "max_drawdown": bt_metrics.get("max_drawdown", 0),   # 이미 양수 (abs 처리됨)
                    "sharpe_ratio": bt_metrics.get("sharpe_ratio", 0),
                    "win_rate": bt_metrics.get("win_rate", 0),
                    "profit_factor": bt_metrics.get("profit_factor", 0),
                    "total_trades": bt_metrics.get("total_trades", 0),
                }
                # calculate_trinity_score는 소수 기준을 기대하므로 /100 변환 필요
                trinity_score = calculate_trinity_score(
                    metrics["total_return"] / 100,
                    metrics["sharpe_ratio"],
                    -metrics["max_drawdown"] / 100,   # 양수 퍼센트 → 음수 소수
                )
                results.append({"params": param_values, "metrics": metrics, "trinity_score": trinity_score})

                param_str = ", ".join(f"{k}={v}" for k, v in param_values.items())
                ret = metrics["total_return"]
                yield format_sse({
                    "type": "status",
                    "content": f"⚙️ ({idx+1}/{len(param_grid)}) {param_str} → 수익률 {ret:+.2f}%"
                })
            except Exception as e:
                logger.error(f"백테스트 실패 조합 {idx+1}: {e}")
                yield format_sse({
                    "type": "status",
                    "content": f"⚠️ ({idx+1}/{len(param_grid)}) 실패: {str(e)[:60]}"
                })

        if not results:
            yield format_sse({"type": "analysis", "content": "❌ 모든 파라미터 조합 백테스트가 실패했습니다."})
            yield format_sse({"type": "done"})
            return

        # ── Stage 3: 최적값 선택 + 결과 표시 ──────────────────────
        yield format_sse({"type": "stage", "stage": 3, "label": "🏆 최적 파라미터 선택 중..."})

        results.sort(key=lambda x: x["trinity_score"], reverse=True)
        best = results[0]
        worst = results[-1]
        best_m = best["metrics"]
        worst_m = worst["metrics"]

        # 최적 파라미터 요약 텍스트
        best_params_str = ", ".join(f"`{k}` = **{v}**" for k, v in best["params"].items())
        improvement = best_m["total_return"] - worst_m["total_return"]
        summary_lines = [
            f"## 🏆 최적 파라미터",
            f"{best_params_str}",
            f"",
            f"| 지표 | 기존 | 최적 | 개선 |",
            f"|------|------|------|------|",
            f"| 수익률 | {worst_m['total_return']:+.2f}% | {best_m['total_return']:+.2f}% | {improvement:+.2f}% |",
            f"| Sharpe | {worst_m['sharpe_ratio']:.2f} | {best_m['sharpe_ratio']:.2f} | {best_m['sharpe_ratio']-worst_m['sharpe_ratio']:+.2f} |",
            f"| Win Rate | {worst_m['win_rate']:.1f}% | {best_m['win_rate']:.1f}% | — |",
            f"| MDD | {worst_m['max_drawdown']:.2f}% | {best_m['max_drawdown']:.2f}% | — |",
            f"| 거래 수 | {int(worst_m['total_trades'])} | {int(best_m['total_trades'])} | — |",
        ]
        yield format_sse({"type": "analysis", "content": "\n".join(summary_lines)})

        # 최적 파라미터 적용 코드를 backtest 카드로 표시
        best_code = _apply_params_to_code(strategy_code, best["params"])
        yield format_sse({
            "type": "backtest",
            "data": {
                "ret": f"{best_m['total_return']:+.2f}%",
                "mdd": f"{abs(best_m['max_drawdown']):.2f}%",
                "winRate": f"{best_m['win_rate']:.1f}%",
                "sharpe": f"{best_m['sharpe_ratio']:.2f}",
                "code": best_code,
                "trades": int(best_m["total_trades"]),
                "pf": f"{best_m['profit_factor']:.2f}",
            },
            "payload": None,
        })

        yield format_sse({"type": "done"})

    except Exception as e:
        logger.exception(f"파라미터 최적화 파이프라인 오류: {e}")
        yield format_sse({
            "type": "error",
            "content": f"❌ 파이프라인 오류: {str(e)}"
        })
