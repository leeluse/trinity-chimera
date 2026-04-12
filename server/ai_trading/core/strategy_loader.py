import ast
import multiprocessing
from dataclasses import dataclass
from abc import update_abstractmethods
from typing import Type, Any, Dict
import pandas as pd
from server.ai_trading.core.strategy_interface import StrategyInterface

class SecurityError(Exception):
    """전략에서 안전하지 않은 코드가 감지되었을 때 발생합니다."""
    pass

@dataclass
class CompatSignal:
    """Compatibility signal schema for legacy strategy templates."""
    entry: bool = False
    exit: bool = False
    direction: str = "long"
    strength: float = 1.0
    stop_loss: float = None
    take_profit: float = None


def _normalize_signal_value(raw: Any) -> int:
    """Normalize various signal payloads into -1/0/1 for BacktestManager."""
    if raw is None:
        return 0

    if isinstance(raw, bool):
        return 1 if raw else 0

    if isinstance(raw, (int, float)):
        return 1 if raw > 0 else -1 if raw < 0 else 0

    if isinstance(raw, dict):
        signal_value = raw.get("signal")
        if isinstance(signal_value, (int, float)):
            return 1 if signal_value > 0 else -1 if signal_value < 0 else 0
        entry = bool(raw.get("entry", False))
        exit_signal = bool(raw.get("exit", False))
        direction = str(raw.get("direction", "long")).lower()
        if entry:
            return 1 if direction != "short" else -1
        if exit_signal:
            return -1
        return 0

    signal_attr = getattr(raw, "signal", None)
    if isinstance(signal_attr, (int, float)):
        return 1 if signal_attr > 0 else -1 if signal_attr < 0 else 0

    entry = bool(getattr(raw, "entry", False))
    exit_signal = bool(getattr(raw, "exit", False))
    direction = str(getattr(raw, "direction", "long")).lower()
    if entry:
        return 1 if direction != "short" else -1
    if exit_signal:
        return -1
    return 0


class CompatStrategyBase(StrategyInterface):
    """
    Compatibility shim for legacy code that implements generate_signals(data, params).
    """

    def generate_signals(self, data: pd.DataFrame, params: Dict[str, Any]) -> Any:
        raise NotImplementedError("generate_signals must be implemented by strategy")

    def generate_signal(self, data: pd.DataFrame) -> int:
        params = self.get_params()
        try:
            raw_signal = self.generate_signals(data, params)
        except TypeError:
            # Fallback for generate_signals(self, data) style implementations.
            raw_signal = self.generate_signals(data)
        return _normalize_signal_value(raw_signal)

    def get_params(self) -> Dict[str, Any]:
        for attr in ("params", "default_params", "config", "CONFIG"):
            value = getattr(self, attr, None)
            if isinstance(value, dict):
                return dict(value)
        return {}


def _build_exec_namespace() -> Dict[str, Any]:
    return {
        "StrategyInterface": StrategyInterface,
        "Strategy": CompatStrategyBase,
        "Signal": CompatSignal,
        "pd": pd,
    }


def _strategy_target(queue, code, class_name, data_obj):
    try:
        # 동적으로 생성된 클래스의 피클링 문제를 피하기 위해 자식 프로세스에서 전략을 다시 로드합니다.
        namespace = _build_exec_namespace()
        exec(code, namespace)
        strategy_class = namespace.get(class_name)
        if not strategy_class:
            queue.put(RuntimeError(f"자식 프로세스에서 {class_name} 클래스를 찾을 수 없습니다"))
            return

        StrategyLoader._ensure_strategy_interface_compat(strategy_class)
        strategy_instance = strategy_class()
        result = strategy_instance.generate_signal(data_obj)
        queue.put(result)
    except Exception as e:
        queue.put(e)

class StrategyLoader:
    """
    LLM이 생성한 트레이딩 전략을 로드하고 검증합니다.
    """


    FORBIDDEN_NODES = {
        ast.Import,
        ast.ImportFrom
    }

    FORBIDDEN_MODULES = {
        'os', 'sys', 'subprocess', 'shutil', 'socket', 'pickle', 'threading', 'multiprocessing'
    }

    # Allow only a narrow set of imports used by generated quant strategies.
    # Everything else is blocked early to avoid runtime ModuleNotFound errors.
    ALLOWED_MODULE_PREFIXES = {
        "pandas",
        "numpy",
        "math",
        "typing",
        "collections",
        "dataclasses",
        "statistics",
        "functools",
        "itertools",
        "datetime",
        "server.ai_trading.core.strategy_interface",
    }

    FORBIDDEN_FUNCTIONS = {
        'open', 'eval', 'exec', '__import__'
    }

    @classmethod
    def validate_code(cls, code: str):
        """
        악성 실행을 방지하기 위해 AST를 사용하여 제공된 파이썬 코드를 검증합니다.
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            raise SecurityError(f"전략 코드에 구문 오류가 있습니다: {e}")

        for node in ast.walk(tree):
            # 금지된 임포트 확인
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = str(alias.name or "").strip()
                    if not module_name:
                        raise SecurityError("비어있는 모듈 임포트는 허용되지 않습니다.")
                    if cls._is_forbidden_module(module_name):
                        raise SecurityError(f"금지된 모듈 임포트: {module_name}")
                    if not cls._is_allowed_module(module_name):
                        raise SecurityError(f"허용되지 않은 모듈 임포트: {module_name}")

            elif isinstance(node, ast.ImportFrom):
                module_name = str(node.module or "").strip()
                if not module_name:
                    raise SecurityError("상대 경로 임포트는 허용되지 않습니다.")
                if cls._is_forbidden_module(module_name):
                    raise SecurityError(f"금지된 모듈로부터의 임포트: {module_name}")
                if not cls._is_allowed_module(module_name):
                    raise SecurityError(f"허용되지 않은 모듈로부터의 임포트: {module_name}")

            # 금지된 함수 호출 확인
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in cls.FORBIDDEN_FUNCTIONS:
                        raise SecurityError(f"금지된 함수 호출: {node.func.id}")
                elif isinstance(node.func, ast.Attribute):
                    if node.func.attr in cls.FORBIDDEN_FUNCTIONS:
                        raise SecurityError(f"금지된 속성 호출: {node.func.attr}")

        return True

    @classmethod
    def _is_forbidden_module(cls, module_name: str) -> bool:
        return any(
            module_name == blocked or module_name.startswith(f"{blocked}.")
            for blocked in cls.FORBIDDEN_MODULES
        )

    @classmethod
    def _is_allowed_module(cls, module_name: str) -> bool:
        return any(
            module_name == allowed or module_name.startswith(f"{allowed}.")
            for allowed in cls.ALLOWED_MODULE_PREFIXES
        )

    @classmethod
    def load_strategy(cls, code: str, class_name: str) -> StrategyInterface:
        """
        코드를 검증하고 전략 클래스를 동적으로 로드합니다.
        """
        cls.validate_code(code)

        # 제어된 네임스페이스에서 코드를 실행합니다.
        namespace = _build_exec_namespace()
        try:
            exec(code, namespace)
        except Exception as e:
            raise SecurityError(f"전략 코드 실행 중 오류 발생: {e}")

        strategy_class = namespace.get(class_name)
        if not strategy_class:
            raise SecurityError(f"제공된 코드에서 {class_name} 클래스를 찾을 수 없습니다.")

        cls._ensure_strategy_interface_compat(strategy_class)

        if not issubclass(strategy_class, StrategyInterface):
            raise SecurityError(f"{class_name} 클래스는 반드시 StrategyInterface를 상속받아야 합니다.")

        return strategy_class()

    @staticmethod
    def _ensure_strategy_interface_compat(strategy_class: Type[Any]) -> None:
        """
        Add missing StrategyInterface methods for legacy templates before instantiation.
        """
        abstract_methods = set(getattr(strategy_class, "__abstractmethods__", set()))
        patched = False

        if "generate_signal" in abstract_methods and callable(getattr(strategy_class, "generate_signals", None)):
            def generate_signal(self, data):
                params = self.get_params() if callable(getattr(self, "get_params", None)) else {}
                try:
                    raw_signal = self.generate_signals(data, params)
                except TypeError:
                    raw_signal = self.generate_signals(data)
                return _normalize_signal_value(raw_signal)

            setattr(strategy_class, "generate_signal", generate_signal)
            patched = True

        if "get_params" in abstract_methods:
            def get_params(self):
                for attr in ("params", "default_params", "config", "CONFIG"):
                    value = getattr(self, attr, None)
                    if isinstance(value, dict):
                        return dict(value)
                return {}

            setattr(strategy_class, "get_params", get_params)
            patched = True

        if patched:
            update_abstractmethods(strategy_class)

    @staticmethod
    def execute_with_timeout(strategy: StrategyInterface, code: str, class_name: str, data: Any, timeout: int = 30) -> Any:
        """
        엄격한 타임아웃을 적용하여 전략의 generate_signal 메서드를 실행합니다.
        자식 프로세스에서 다시 인스턴스화하기 위해 원본 코드와 클래스 이름이 필요합니다.
        """
        queue = multiprocessing.Queue()
        process = multiprocessing.Process(target=_strategy_target, args=(queue, code, class_name, data))
        process.start()

        try:
            # 타임아웃 내에 결과 대기
            result = queue.get(timeout=timeout)
            if isinstance(result, Exception):
                raise result
            return result
        except Exception as e:
            process.terminate()
            process.join()
            if isinstance(e, multiprocessing.queues.Empty):
                raise TimeoutError(f"전략 실행이 {timeout}초 후에 타임아웃되었습니다.")
            raise e
        finally:
            if process.is_alive():
                process.terminate()
                process.join()
