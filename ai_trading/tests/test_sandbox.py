import unittest
import pandas as pd
import time
from ai_trading.core.strategy_interface import StrategyInterface
from ai_trading.core.strategy_loader import StrategyLoader, SecurityError

# 유효한 전략 코드
VALID_STRATEGY_CODE = """
from ai_trading.core.strategy_interface import StrategyInterface
import pandas as pd

class ValidStrategy(StrategyInterface):
    def generate_signal(self, data):
        return 1 if data['close'].iloc[-1] > data['close'].iloc[-2] else 0

    def get_params(self):
        return {"param": "value"}
"""

# 악성 전략 코드 (os 모듈 사용 시도)
MALICIOUS_STRATEGY_CODE = """
from ai_trading.core.strategy_interface import StrategyInterface
import os

class MaliciousStrategy(StrategyInterface):
    def generate_signal(self, data):
        os.system('echo hacked')
        return 1

    def get_params(self):
        return {}
"""

# 무한 루프 전략 코드
INFINITE_STRATEGY_CODE = """
from ai_trading.core.strategy_interface import StrategyInterface

class InfiniteStrategy(StrategyInterface):
    def generate_signal(self, data):
        while True:
            pass
        return 1

    def get_params(self):
        return {}
"""

class TestSandbox(unittest.TestCase):
    def setUp(self):
        self.data = pd.DataFrame({'close': [100, 110]})

    def test_valid_strategy_load_and_exec(self):
        strategy = StrategyLoader.load_strategy(VALID_STRATEGY_CODE, "ValidStrategy")
        self.assertIsInstance(strategy, StrategyInterface)

        result = StrategyLoader.execute_with_timeout(strategy, VALID_STRATEGY_CODE, "ValidStrategy", self.data)
        self.assertEqual(result, 1)

    def test_security_block_import(self):
        with self.assertRaises(SecurityError) as cm:
            StrategyLoader.load_strategy(MALICIOUS_STRATEGY_CODE, "MaliciousStrategy")
        self.assertIn("Forbidden module import: os", str(cm.exception))

    def test_security_block_open(self):
        code = """
from ai_trading.core.strategy_interface import StrategyInterface
class OpenStrategy(StrategyInterface):
    def generate_signal(self, data):
        open('test.txt', 'w')
        return 1
    def get_params(self): return {}
"""
        with self.assertRaises(SecurityError) as cm:
            StrategyLoader.load_strategy(code, "OpenStrategy")
        self.assertIn("Forbidden function call: open", str(cm.exception))

    def test_timeout_termination(self):
        strategy = StrategyLoader.load_strategy(INFINITE_STRATEGY_CODE, "InfiniteStrategy")
        with self.assertRaises(TimeoutError):
            StrategyLoader.execute_with_timeout(strategy, INFINITE_STRATEGY_CODE, "InfiniteStrategy", self.data, timeout=2)

if __name__ == "__main__":
    unittest.main()
