import unittest
import pandas as pd
import time
from server.ai_trading.core.strategy_interface import StrategyInterface
from server.ai_trading.core.strategy_loader import StrategyLoader, SecurityError

# 유효한 전략 코드
VALID_STRATEGY_CODE = """
from server.ai_trading.core.strategy_interface import StrategyInterface
import pandas as pd

class ValidStrategy(StrategyInterface):
    def generate_signal(self, data):
        return 1 if data['close'].iloc[-1] > data['close'].iloc[-2] else 0

    def get_params(self):
        return {"param": "value"}
"""

# 악성 전략 코드 (os 모듈 사용 시도)
MALICIOUS_STRATEGY_CODE = """
from server.ai_trading.core.strategy_interface import StrategyInterface
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
from server.ai_trading.core.strategy_interface import StrategyInterface

class InfiniteStrategy(StrategyInterface):
    def generate_signal(self, data):
        while True:
            pass
        return 1

    def get_params(self):
        return {}
"""

LEGACY_SIGNAL_STYLE_CODE = """
class LegacyBreakout(Strategy):
    params = {"period": 20}

    def generate_signals(self, data, params):
        if len(data) < 2:
            return Signal()
        if data['close'].iloc[-1] > data['close'].iloc[-2]:
            return Signal(entry=True, direction="long")
        return Signal(exit=True)
"""

ABSTRACT_METHOD_COMPAT_CODE = """
class PatchedStrategy(StrategyInterface):
    default_params = {"k": 1}

    def generate_signals(self, data, params):
        return {"entry": True, "direction": "long"}
"""

UNKNOWN_IMPORT_CODE = """
import lettrade

class ThirdPartyStrategy(StrategyInterface):
    def generate_signal(self, data):
        return 0

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
        self.assertIn("금지된 모듈 임포트: os", str(cm.exception))

    def test_security_block_open(self):
        code = """
from server.ai_trading.core.strategy_interface import StrategyInterface
class OpenStrategy(StrategyInterface):
    def generate_signal(self, data):
        open('test.txt', 'w')
        return 1
    def get_params(self): return {}
"""
        with self.assertRaises(SecurityError) as cm:
            StrategyLoader.load_strategy(code, "OpenStrategy")
        self.assertIn("금지된 함수 호출: open", str(cm.exception))

    def test_timeout_termination(self):
        strategy = StrategyLoader.load_strategy(INFINITE_STRATEGY_CODE, "InfiniteStrategy")
        with self.assertRaises(TimeoutError):
            StrategyLoader.execute_with_timeout(strategy, INFINITE_STRATEGY_CODE, "InfiniteStrategy", self.data, timeout=2)

    def test_legacy_generate_signals_compat(self):
        strategy = StrategyLoader.load_strategy(LEGACY_SIGNAL_STYLE_CODE, "LegacyBreakout")
        self.assertIsInstance(strategy, StrategyInterface)

        up_data = pd.DataFrame({'close': [100, 101]})
        down_data = pd.DataFrame({'close': [101, 100]})
        self.assertEqual(strategy.generate_signal(up_data), 1)
        self.assertEqual(strategy.generate_signal(down_data), -1)
        self.assertEqual(strategy.get_params().get("period"), 20)

    def test_patch_abstract_methods_from_generate_signals(self):
        strategy = StrategyLoader.load_strategy(ABSTRACT_METHOD_COMPAT_CODE, "PatchedStrategy")
        self.assertIsInstance(strategy, StrategyInterface)
        self.assertEqual(strategy.generate_signal(self.data), 1)
        self.assertEqual(strategy.get_params().get("k"), 1)

    def test_security_block_unknown_module_import(self):
        with self.assertRaises(SecurityError) as cm:
            StrategyLoader.load_strategy(UNKNOWN_IMPORT_CODE, "ThirdPartyStrategy")
        self.assertIn("허용되지 않은 모듈 임포트: lettrade", str(cm.exception))

if __name__ == "__main__":
    unittest.main()
