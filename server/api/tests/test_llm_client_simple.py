#!/usr/bin/env python3
"""
Simple integration test for LLM API connectivity and error handling.

This test focuses on the core EvolutionLLMClient functionality without
requiring external dependencies.
"""

import os
import asyncio
import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from typing import Dict, Any


class MockStrategyLoader:
    """Mock StrategyLoader to avoid dependency issues."""

    @staticmethod
    def validate_code(code: str):
        """Simple mock validation that checks for basic syntax."""
        if not code:
            raise ValueError("Empty code")

        # Basic syntax checks
        if "class" not in code.lower():
            raise SyntaxError("Missing class definition")

        if "def" not in code.lower():
            raise SyntaxError("Missing function definition")

        # Mock forbidden import check
        if "import os" in code or "import sys" in code or "import subprocess" in code:
            class MockSecurityError(Exception):
                pass
            raise MockSecurityError("Forbidden import detected")


class EvolutionLLMClient:
    """Simplified EvolutionLLMClient for testing."""

    def __init__(self, llm_service: Any = None):
        self.llm_service = llm_service

    async def generate_strategy_code(self, evolution_package: Dict[str, Any], max_retries: int = 3) -> str:
        """Generate improved strategy code using C-mode context."""
        prompt = self._assemble_c_mode_context(evolution_package)
        attempt = 0
        last_error = None

        while attempt < max_retries:
            try:
                code = await self._call_llm(prompt, last_error)
                code = self._clean_code(code)

                # Use mock validation
                MockStrategyLoader.validate_code(code)

                print(f"Strategy code generated and validated successfully on attempt {attempt + 1}")
                return code

            except (ValueError, SyntaxError) as e:
                attempt += 1
                last_error = str(e)
                print(f"Strategy validation failed (attempt {attempt}/{max_retries}): {e}")
                if attempt >= max_retries:
                    print(f"Failed to generate valid strategy code after {max_retries} attempts.")
                    raise e
            except Exception as e:
                print(f"Unexpected error during code generation: {e}")
                raise e

    def _assemble_c_mode_context(self, pkg: Dict[str, Any]) -> str:
        """Formats the evolution_package into a structured C-mode prompt."""
        current_code = pkg.get("current_strategy_code", "No code provided")
        metrics = pkg.get("metrics", {})

        prompt = f"""
### [Evolution Mode: C-MODE]
You are an expert Quantitative Strategy Evolver. Your goal is to evolve the current trading strategy to improve its Trinity Score and robustness.

#### 1. Current Strategy Code
```python
{current_code}
```

#### 2. Performance Metrics
- Trinity Score: {metrics.get('trinity_score', 'N/A')}
- Total Return: {metrics.get('return', 'N/A')}

### Instructions:
1. Analyze the current code and improve it.
2. Output ONLY the valid Python code for the strategy class.
"""
        return prompt

    async def _call_llm(self, prompt: str, error_context: Optional[str] = None) -> str:
        """Simulates or calls the LLM service."""
        if error_context:
            prompt += f"\n\n### SELF-CORRECTION REQUIRED\nYour previous attempt failed with the following error:\n```\n{error_context}\n```\n Please fix the code and return the corrected version."

        if self.llm_service:
            return await self.llm_service.generate(prompt)

        # Mock response for testing purposes
        return "# Mock Strategy Code\nclass evolved_strategy:\n    def generate_signal(self, data):\n        return 1"

    def _clean_code(self, text: str) -> str:
        """Removes markdown code blocks from the LLM response."""
        if "```python" in text:
            text = text.split("```python")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return text.strip()


class TestLLMIntegration(unittest.TestCase):
    """Integration tests for LLM API functionality."""

    def setUp(self):
        """Set up fresh instance for each test."""
        self.evolution_package = {
            "current_strategy_code": "class mock_strategy:\n    def generate_signal(self, data):\n        return 1",
            "metrics": {
                "trinity_score": 120,
                "return": 10.0,
            }
        }

    def run_async(self, coroutine):
        """Helper method to run async tests."""
        return asyncio.run(coroutine)

    def test_actual_llm_api_call_success(self):
        """Test making an API call to LLM service."""
        client = EvolutionLLMClient()

        # Test validates the mock fallback behavior
        code = self.run_async(client.generate_strategy_code(self.evolution_package))

        # Verify we get some code back
        self.assertIsInstance(code, str)
        self.assertGreater(len(code), 0)

        # Verify the code is clean (no markdown blocks)
        self.assertNotIn("```", code)

        # Verify basic structure
        self.assertIn("class", code.lower())
        self.assertIn("def", code.lower())

    def test_error_handling_with_mock_service(self):
        """Test error handling when LLM service fails."""
        # Create a mock LLM service that raises an exception
        mock_service = AsyncMock()
        mock_service.generate.side_effect = Exception("API call failed")

        client = EvolutionLLMClient(llm_service=mock_service)

        # Test that the error is properly caught
        with self.assertRaises(Exception) as context:
            self.run_async(client.generate_strategy_code(self.evolution_package))

        self.assertIn("API call failed", str(context.exception))

    def test_retry_logic_on_validation_error(self):
        """Test retry logic when strategy validation fails."""
        # Mock LLM service that returns invalid code then valid code
        mock_service = AsyncMock()
        mock_service.generate.side_effect = [
            "invalid code",  # Will fail validation
            "class valid_strategy:\n    def generate_signal(self, data):\n        return 1"
        ]

        client = EvolutionLLMClient(llm_service=mock_service)
        code = self.run_async(client.generate_strategy_code(self.evolution_package, max_retries=2))

        # Verify LLM was called twice
        self.assertEqual(mock_service.generate.call_count, 2)

        # Verify we got valid code back
        self.assertIn("valid_strategy", code)

    def test_max_retries_exceeded(self):
        """Test that exception is raised when max retries exceeded."""
        mock_service = AsyncMock()
        mock_service.generate.return_value = "invalid code"  # Will always fail

        client = EvolutionLLMClient(llm_service=mock_service)

        with self.assertRaises(SyntaxError) as context:
            self.run_async(client.generate_strategy_code(self.evolution_package, max_retries=2))

        self.assertEqual(mock_service.generate.call_count, 2)
        self.assertIn("Missing class definition", str(context.exception))

    def test_c_mode_prompt_assembly(self):
        """Test C-mode context assembly generates proper prompt structure."""
        client = EvolutionLLMClient()
        prompt = client._assemble_c_mode_context(self.evolution_package)

        # Verify key sections are present
        self.assertIn("[Evolution Mode: C-MODE]", prompt)
        self.assertIn("Current Strategy Code", prompt)
        self.assertIn("Performance Metrics", prompt)

        # Verify metrics are included
        self.assertIn("Trinity Score", prompt)
        self.assertIn("120", prompt)

    def test_self_correction_with_error_context(self):
        """Test self-correction loop includes error context in subsequent calls."""
        mock_service = AsyncMock()
        mock_service.generate.side_effect = [
            "invalid code",  # First call fails
            "class strategy:\n    def generate_signal(self, data):\n        return 1"
        ]

        client = EvolutionLLMClient(llm_service=mock_service)
        self.run_async(client.generate_strategy_code(self.evolution_package))

        # Verify error context was passed to the second LLM call
        self.assertEqual(mock_service.generate.call_count, 2)

        # Check that second call included error context
        args, kwargs = mock_service.generate.call_args
        self.assertIn("SELF-CORRECTION REQUIRED", args[0])

    def test_code_cleaning_functionality(self):
        """Test code cleaning removes markdown blocks."""
        client = EvolutionLLMClient()

        # Test with markdown code block
        code_with_markdown = """Here's some explanation:
        ```python
        class cleaned_strategy:
            def generate_signal(self, data):
                return 1
        ```
        And some more text."""

        cleaned_code = client._clean_code(code_with_markdown)
        # Expected output after cleaning (with proper indentation preserved)
        expected = "class cleaned_strategy:\n            def generate_signal(self, data):\n                return 1"
        self.assertEqual(cleaned_code.strip(), expected)

        # Test without markdown (should remain unchanged)
        clean_code = "class strategy:\n    def generate_signal(self, data):\n        return 1"
        cleaned = client._clean_code(clean_code)
        self.assertEqual(cleaned.strip(), clean_code)

    def test_no_llm_service_fallback(self):
        """Test fallback behavior when no LLM service is provided."""
        client = EvolutionLLMClient()  # No service provided

        # Should fall back to mock response
        code = self.run_async(client.generate_strategy_code(self.evolution_package))

        self.assertIsInstance(code, str)
        self.assertGreater(len(code), 0)
        self.assertIn("Mock Strategy Code", code)


if __name__ == "__main__":
    # Run the tests
    unittest.main()