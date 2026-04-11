# server/ai_trading/tests/test_scoring.py
"""Trinity Score v2 단위 테스트"""

import pytest
from server.ai_trading.core.scoring import calculate_trinity_score_v2


class TestTrinityScoreV2:
    """Trinity Score v2 테스트 suite"""

    def test_trinity_score_v2_calculation(self):
        """기본 계산 테스트 - 알려진 값으로 검증"""
        result = calculate_trinity_score_v2(
            return_val=0.15,      # 15% return
            sharpe=2.0,           # Sharpe ratio
            mdd=-0.05,            # -5% max drawdown
            profit_factor=1.5,    # Profit factor
            win_rate=0.6          # 60% win rate
        )

        expected = (0.15 * 0.30) + \
                   (2.0 * 25 * 0.25) + \
                   ((1 - 0.05) * 100 * 0.20) + \
                   (1.5 * 20 * 0.15) + \
                   (0.6 * 100 * 0.10)

        assert result == round(expected, 4)

    def test_trinity_score_v2_edge_cases(self):
        """엣지 케이스 테스트"""
        # Test zero values
        result = calculate_trinity_score_v2(0, 0, 0, 0, 0)
        assert result == 20.0  # (1 + 0) * 100 * 0.20 = 20

        # Test negative return
        result = calculate_trinity_score_v2(-0.1, 1.0, -0.1, 0.8, 0.4)
        assert result < 50.0  # Should be lower due to negative return

    def test_trinity_score_v2_with_positive_mdd(self):
        """양수 MDD 처리 테스트 - 음수로 변환"""
        # MDD가 양수로 전달되면 음수로 변환되어야 함
        result_negative = calculate_trinity_score_v2(
            return_val=0.15, sharpe=2.0, mdd=-0.05, profit_factor=1.5, win_rate=0.6
        )
        result_positive = calculate_trinity_score_v2(
            return_val=0.15, sharpe=2.0, mdd=0.05, profit_factor=1.5, win_rate=0.6
        )

        # 양수든 음수든 결과는 같아야 함
        assert result_negative == result_positive

    def test_trinity_score_v2_all_metrics(self):
        """모든 지표가 포함된 계산 테스트"""
        result = calculate_trinity_score_v2(
            return_val=0.20,      # 20%
            sharpe=1.5,           # Sharpe 1.5
            mdd=-0.10,            # -10% MDD
            profit_factor=2.0,    # PF 2.0
            win_rate=0.55         # 55% Win Rate
        )

        # 수동 계산 검증
        expected = (0.20 * 0.30) + \
                   (1.5 * 25 * 0.25) + \
                   ((1 - 0.10) * 100 * 0.20) + \
                   (2.0 * 20 * 0.15) + \
                   (0.55 * 100 * 0.10)

        assert result == round(expected, 4)
        assert result > 0  # 모든 양수 기여로 인해 결과는 양수

    def test_trinity_score_v2_weight_verification(self):
        """가중치 검증 테스트"""
        # 각 가중치가 정확히 적용되는지 확인
        # Return: 0.30
        # Sharpe * 25: 0.25
        # MDD: 0.20
        # PF * 20: 0.15
        # WinRate * 100: 0.10

        result = calculate_trinity_score_v2(0.30, 1.0, -0.10, 1.0, 0.50)

        expected = (0.30 * 0.30) + \
                   (1.0 * 25 * 0.25) + \
                   ((1 - 0.10) * 100 * 0.20) + \
                   (1.0 * 20 * 0.15) + \
                   (0.50 * 100 * 0.10)

        assert result == round(expected, 4)

    def test_trinity_score_v2_range(self):
        """점수 범위 테스트 - 일반적인 값들의 범위 확인"""
        # 낮은 성과
        low_score = calculate_trinity_score_v2(-0.2, 0.5, -0.5, 0.5, 0.3)

        # 중간 성과
        mid_score = calculate_trinity_score_v2(0.1, 1.5, -0.15, 1.5, 0.55)

        # 높은 성과
        high_score = calculate_trinity_score_v2(0.5, 3.0, -0.05, 3.0, 0.8)

        assert low_score < mid_score < high_score
