# server/ai_trading/core/scoring.py
"""
Trinity Score v2 단일 소스 정의

이 모듈은 Trinity AI Trading System의 통합 성과 지표를 계산합니다.
모든 계산은 이 파일에서 정의된 공식을 따라야 합니다.

Trinity Score v2 공식:
    Return × 0.30 +
    Sharpe × 25 × 0.25 +
    (1 + MDD) × 100 × 0.20 +
    PF × 20 × 0.15 +
    WinRate × 100 × 0.10

참고:
    - MDD는 음수 값으로 계산됩니다 (예: -5% = -0.05)
    - MDD가 양수로 전달되면 자동으로 음수로 변환됩니다
    - 결과는 소수점 4자리까지 반올림됩니다
"""

from typing import Union

Numeric = Union[float, int]


def calculate_trinity_score_v2(
    return_val: Numeric,
    sharpe: Numeric,
    mdd: Numeric,
    profit_factor: Numeric,
    win_rate: Numeric
) -> float:
    """
    Trinity Score v2 계산

    Args:
        return_val: 총 수익률 (예: 0.15 = 15%)
        sharpe: 샤프 비율
        mdd: 최대 낙폭 (예: -0.05 = -5%)
        profit_factor: Profit Factor (총 이익 / 총 손실)
        win_rate: 승률 (예: 0.6 = 60%)

    Returns:
        float: Trinity Score (소수점 4자리 반올림)

    Example:
        >>> calculate_trinity_score_v2(0.15, 2.0, -0.05, 1.5, 0.6)
        76.9
    """
    # MDD가 양수로 전달되면 음수로 변환
    if mdd > 0:
        mdd = -mdd

    # Profit Factor 캡핑 (0.5 ~ 10 범위)
    profit_factor = max(0.5, min(profit_factor, 10))

    # Sharpe 캡핑 (0 ~ 10 범위)
    sharpe = max(0, min(sharpe, 10))

    # Return 캡핑 (-1 ~ 2 범위)
    return_val = max(-1, min(return_val, 2))

    score = (
        (return_val * 0.30) +
        (sharpe * 25 * 0.25) +
        ((1 + mdd) * 100 * 0.20) +
        (profit_factor * 20 * 0.15) +
        (win_rate * 100 * 0.10)
    )

    return round(score, 4)


def calculate_trinity_score_legacy(
    return_val: Numeric,
    sharpe: Numeric,
    mdd: Numeric
) -> float:
    """
    Trinity Score v1 (레거시) - 하위 호환성 유지

    기존 공식:
        Return × 0.40 + Sharpe × 25 × 0.35 + (1 + MDD) × 100 × 0.25

    Note:
        새로운 코드에서는 calculate_trinity_score_v2를 사용하세요.
    """
    if mdd > 0:
        mdd = -mdd

    score = (
        (return_val * 0.40) +
        (sharpe * 25 * 0.35) +
        ((1 + mdd) * 100 * 0.25)
    )

    return round(score, 4)
