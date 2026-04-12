import pytest
import asyncio
from unittest.mock import MagicMock, patch
from server.ai_trading.agents.llm_client import EvolutionLLMClient, LLMUnavailableError


class TestEvolutionLLMClient:
    @pytest.fixture
    def client(self):
        return EvolutionLLMClient()

    @pytest.mark.asyncio
    async def test_llm_unavailable_error(self, client):
        """LLM 서비스 없을 때 예외 발생 테스트"""
        with pytest.raises(LLMUnavailableError):
            await client._call_llm("test prompt")

    @pytest.mark.asyncio
    async def test_llm_with_mock_service(self, client):
        """Mock LLM 서비스와의 통합 테스트"""
        mock_service = MagicMock()
        mock_service.generate.return_value = asyncio.Future()
        mock_service.generate.return_value.set_result("mock response")
        client.llm_service = mock_service

        result = await client._call_llm("test prompt")
        assert result == "mock response"

    @pytest.mark.asyncio
    async def test_llm_with_error_context(self, client):
        """에러 컨텍스트 포함 테스트"""
        mock_service = MagicMock()
        mock_service.generate.return_value = asyncio.Future()
        mock_service.generate.return_value.set_result("corrected code")
        client.llm_service = mock_service

        error_context = "SyntaxError: invalid syntax"
        result = await client._call_llm("test prompt", error_context)

        # 에러 컨텍스트가 프롬프트에 포함되었는지 확인
        assert mock_service.generate.called
        call_args = mock_service.generate.call_args[0][0]
        assert "SELF-CORRECTION REQUIRED" in call_args
        assert error_context in call_args

    def test_clean_code_extraction(self, client):
        """코드 블록 추출 테스트"""
        # Python 코드 블록이 있는 텍스트
        text_with_code = """
Here's the strategy code:
```python
class TestStrategy:
    def generate_signal(self, data):
        return 1
```
"""
        result = client._clean_code(text_with_code)
        assert "class TestStrategy:" in result
        assert "```python" not in result

    def test_clean_code_no_code_block(self, client):
        """코드 블록 없는 텍스트 처리 테스트"""
        text_without_code = "Just plain text"
        result = client._clean_code(text_without_code)
        assert result == "Just plain text"

    @pytest.mark.asyncio
    async def test_generate_strategy_code_with_retries(self, client):
        """재시도 로직 테스트"""
        mock_service = MagicMock()

        # 첫 번째 호출에서 SyntaxError, 두 번째 호출에서 성공
        async def mock_generate(prompt):
            if mock_generate.call_count == 0:
                mock_generate.call_count += 1
                return "invalid python code"  # 첫 번째 호출 - 검증 실패
            else:
                return "class ValidStrategy:\n    pass"  # 두 번째 호출 - 성공

        mock_generate.call_count = 0
        mock_service.generate = mock_generate
        client.llm_service = mock_service

        evolution_package = {
            "current_strategy_code": "class OldStrategy:\n    pass",
            "metrics": {"trinity_score": 75.0},
            "loss_period_logs": "test logs"
        }

        result = await client.generate_strategy_code(evolution_package)
        assert result == "class ValidStrategy:\n    pass"
        # 첫 번째는 실패하고 두 번째에서 성공하므로 2번 호출
        assert mock_generate.call_count >= 1
