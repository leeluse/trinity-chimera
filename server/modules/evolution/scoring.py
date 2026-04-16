# Scoring Engine
# 전략의 성과를 정량적으로 평가하고 Trinity Score를 산출합니다.

from typing import Dict, Any, List, Tuple

def calculate_trinity_score(
    total_return: float,
    sharpe: float,
    max_drawdown: float,
    win_rate: float = 0
) -> float:
    """
    Trinity Score 공식:
    Return(40%) + Sharpe(35%) + Safety/MDD(25%)
    """
    # 1. Return Component (40%) - 수익률
    return_comp = total_return * 0.4
    
    # 2. Sharpe Component (35%) - 위험 대비 수익률 (샤프 25 기준 정규화)
    sharpe_comp = sharpe * 25 * 0.35
    
    # 3. MDD Component (25%) - 낙폭 방어력 (MDD -30% 이내 시 가점)
    # MDD가 -0.3보다 크면(즉 -20% 등) 더 안전한 것으로 간주
    mdd_val = max(max_drawdown, -0.3)
    mdd_comp = (1 + mdd_val) * 100 * 0.25
    
    return float(return_comp + sharpe_comp + mdd_comp)

def evaluate_improvement(baseline_metrics: Dict[str, Any], candidate_metrics: Dict[str, Any]) -> bool:
    """후보 전략이 기준 전략보다 개선되었는지 판단"""
    baseline_score = calculate_trinity_score(
        baseline_metrics.get('total_return', 0),
        baseline_metrics.get('sharpe_ratio', 0),
        baseline_metrics.get('max_drawdown', 0)
    )
    
    candidate_score = calculate_trinity_score(
        candidate_metrics.get('total_return', 0),
        candidate_metrics.get('sharpe_ratio', 0),
        candidate_metrics.get('max_drawdown', 0)
    )
    
    return candidate_score > baseline_score


def evaluate_hard_gates(
    metrics: Dict[str, Any],
    gates: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """
    Hard gate 평가.
    - 모든 값은 decimal 기준(예: 45% = 0.45)으로 비교
    - max_drawdown은 절대값 기준으로 상한을 검사
    """
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
