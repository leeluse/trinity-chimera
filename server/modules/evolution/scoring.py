# Scoring Engine
# 전략의 성과를 정량적으로 평가하고 Trinity Score를 산출합니다.

from typing import Dict, Any

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
