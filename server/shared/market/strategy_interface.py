from abc import ABC, abstractmethod
import pandas as pd
from typing import Any, Dict

class StrategyInterface(ABC):
    """
    모든 LLM 생성 트레이딩 전략이 반드시 구현해야 하는 추상 베이스 클래스(Abstract Base Class)입니다.
    백테스트 엔진을 위한 일관된 인터페이스를 보장합니다.
    """

    @abstractmethod
    def generate_signal(self, data: pd.DataFrame) -> int:
        """
        제공된 시장 데이터를 분석하여 트레이딩 신호를 생성합니다.

        Args:
            data (pd.DataFrame): 시장 데이터 (OHLCV)

        Returns:
            int: 신호 값 (1 = 매수, -1 = 매도, 0 = 관망)
        """
        pass

    @abstractmethod
    def get_params(self) -> Dict[str, Any]:
        """
        추적 및 최적화를 위한 전략 파라미터를 반환합니다.

        Returns:
            Dict[str, Any]: 전략 파라미터 딕셔너리.
        """
        pass
