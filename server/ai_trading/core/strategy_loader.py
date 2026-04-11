import ast
import multiprocessing
from typing import Type, Any, Dict
from server.ai_trading.core.strategy_interface import StrategyInterface

class SecurityError(Exception):
    """전략에서 안전하지 않은 코드가 감지되었을 때 발생합니다."""
    pass

def _strategy_target(queue, code, class_name, data_obj):
    try:
        # 동적으로 생성된 클래스의 피클링 문제를 피하기 위해 자식 프로세스에서 전략을 다시 로드합니다.
        namespace = {}
        exec(code, namespace)
        strategy_class = namespace.get(class_name)
        if not strategy_class:
            queue.put(RuntimeError(f"자식 프로세스에서 {class_name} 클래스를 찾을 수 없습니다"))
            return

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
                    if alias.name in cls.FORBIDDEN_MODULES:
                        raise SecurityError(f"금지된 모듈 임포트: {alias.name}")

            elif isinstance(node, ast.ImportFrom):
                if node.module in cls.FORBIDDEN_MODULES:
                    raise SecurityError(f"금지된 모듈로부터의 임포트: {node.module}")

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
    def load_strategy(cls, code: str, class_name: str) -> StrategyInterface:
        """
        코드를 검증하고 전략 클래스를 동적으로 로드합니다.
        """
        cls.validate_code(code)

        # 제어된 네임스페이스에서 코드를 실행합니다.
        namespace = {}
        try:
            exec(code, namespace)
        except Exception as e:
            raise SecurityError(f"전략 코드 실행 중 오류 발생: {e}")

        strategy_class = namespace.get(class_name)
        if not strategy_class:
            raise SecurityError(f"제공된 코드에서 {class_name} 클래스를 찾을 수 없습니다.")

        if not issubclass(strategy_class, StrategyInterface):
            raise SecurityError(f"{class_name} 클래스는 반드시 StrategyInterface를 상속받아야 합니다.")

        return strategy_class()

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
