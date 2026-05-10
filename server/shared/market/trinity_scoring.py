from typing import Any, Dict, List, Tuple


def calculate_trinity_score(
    total_return: float,
    sharpe: float,
    max_drawdown: float,
    win_rate: float = 0,
) -> float:
    ret_pct = max(-0.5, min(1.0, total_return))
    return_comp = ((ret_pct + 0.5) / 1.5) * 40.0
    sharpe_comp = max(0.0, min(35.0, (sharpe / 3.0) * 35.0))
    mdd_abs = abs(min(0.0, max_drawdown))
    mdd_comp = max(0.0, (1.0 - mdd_abs / 0.5) * 25.0)
    return float(return_comp + sharpe_comp + mdd_comp)


def evaluate_improvement(baseline_metrics: Dict[str, Any], candidate_metrics: Dict[str, Any]) -> bool:
    baseline_trades = int(baseline_metrics.get("total_trades", 0) or 0)
    candidate_trades = int(candidate_metrics.get("total_trades", 0) or 0)

    if baseline_trades == 0:
        return candidate_trades > 0
    if candidate_trades == 0:
        return False

    baseline_score = calculate_trinity_score(
        baseline_metrics.get("total_return", 0),
        baseline_metrics.get("sharpe_ratio", 0),
        baseline_metrics.get("max_drawdown", 0),
    )
    candidate_score = calculate_trinity_score(
        candidate_metrics.get("total_return", 0),
        candidate_metrics.get("sharpe_ratio", 0),
        candidate_metrics.get("max_drawdown", 0),
    )
    return candidate_score > baseline_score


def evaluate_hard_gates(
    metrics: Dict[str, Any],
    gates: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    reasons: List[str] = []

    win_rate = float(metrics.get("win_rate", 0.0) or 0.0)
    profit_factor = float(metrics.get("profit_factor", 0.0) or 0.0)
    total_return = float(metrics.get("total_return", 0.0) or 0.0)
    max_drawdown_abs = abs(float(metrics.get("max_drawdown", 0.0) or 0.0))
    total_trades = int(metrics.get("total_trades", 0) or 0)
    sharpe_ratio = float(metrics.get("sharpe_ratio", 0.0) or 0.0)

    min_win_rate = float(gates.get("min_win_rate", 0.0))
    min_profit_factor = float(gates.get("min_profit_factor", 0.0))
    min_total_return = float(gates.get("min_total_return", -1.0))
    max_drawdown = float(gates.get("max_drawdown", 1.0))
    min_total_trades = int(gates.get("min_total_trades", 0))
    min_sharpe_ratio = float(gates.get("min_sharpe_ratio", -999.0))

    if win_rate < min_win_rate:
        reasons.append(f"win_rate {win_rate:.3f} < {min_win_rate:.3f}")
    if profit_factor < min_profit_factor:
        reasons.append(f"profit_factor {profit_factor:.3f} < {min_profit_factor:.3f}")
    if total_return < min_total_return:
        reasons.append(f"total_return {total_return:.3f} < {min_total_return:.3f}")
    if max_drawdown_abs > max_drawdown:
        reasons.append(f"|max_drawdown| {max_drawdown_abs:.3f} > {max_drawdown:.3f}")
    if total_trades < min_total_trades:
        reasons.append(f"total_trades {total_trades} < {min_total_trades}")
    if sharpe_ratio < min_sharpe_ratio:
        reasons.append(f"sharpe_ratio {sharpe_ratio:.3f} < {min_sharpe_ratio:.3f}")

    return len(reasons) == 0, reasons
