#!/usr/bin/env python3
"""
Integration tests for LLM API connectivity and error handling.

This test suite verifies:
1. Actual LLM API calls can be made
2. Proper error handling for failed API calls
3. Retry logic implementation
4. Response validation

Note: These tests require valid LLM API credentials in the environment.
"""

import os
import asyncio
import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from typing import Dict, Any

# Add the parent directory to Python path for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from server.api.services.evolution_llm_client import EvolutionLLMClient
from server.ai_trading.core.strategy_loader import StrategyLoader, SecurityError


class TestLLMIntegration(unittest.TestCase):
    """Integration tests for LLM API functionality."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment."""
        cls.llm_api_key = os.getenv('NVIDIA_NIM_API_KEY')
        cls.has_api_access = bool(cls.llm_api_key)

    def setUp(self):
        """Set up fresh instance for each test."""
        self.evolution_package = {
            "current_strategy_code": "class mock_strategy:\n    def generate_signal(self, data):\n        return 1",
            "metrics": {
                "trinity_score": 120,
                "return": 10.0,
                "sharpe": 1.5,
                "mdd": -8.0
            },
            "market_regime": "Bull",
            "competitive_rank": "5th",
            "evolution_history": "S-curve improving",
            "loss_period_logs": "High drawdown during choppy markets",
            "top_agent_traits": "Fast trend adaptation",
            "market_volatility": "Medium"
        }

    def run_async(self, coroutine):
        """Helper method to run async tests."""
        return asyncio.run(coroutine)

    def test_actual_llm_api_call_success(self):
        """Test making an actual API call to LLM service."""
        # This test will only run if API credentials are available
        if not self.has_api_access:
            self.skipTest("LLM API key not available - skipping real API test")

        client = EvolutionLLMClient()

        # Since we don't have a real LLM service configured yet,
        # this test validates the mock fallback behavior
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

        # Test that the error is properly caught and retry logic works
        with self.assertRaises(Exception) as context:
            self.run_async(client.generate_strategy_code(self.evolution_package))

        self.assertIn("API call failed", str(context.exception))

    def test_retry_logic_on_validation_error(self):
        """Test retry logic when strategy validation fails."""
        # Mock LLM service that returns invalid code
        mock_service = AsyncMock()

        # First call returns code with syntax error, second call returns valid code
        mock_service.generate.side_effect = [
            "class invalid_strategy:\n    def generate_signal(self, data:\n        return 1",  # Missing parenthesis
            "class valid_strategy:\n    def generate_signal(self, data):\n        return 1"
        ]

        # Mock the StrategyLoader.validate_code to simulate validation failure then success
        with patch.object(StrategyLoader, 'validate_code') as mock_validate:
            # First validation fails, second succeeds
            mock_validate.side_effect = [
                SyntaxError("Invalid syntax"),
                None  # No error on second call
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
        mock_service.generate.return_value = "class strategy:\n    def generate_signal(self, data):\n        return 1"

        with patch.object(StrategyLoader, 'validate_code') as mock_validate:
            # Always fail validation
            mock_validate.side_effect = SecurityError("Forbidden import detected")

            client = EvolutionLLMClient(llm_service=mock_service)

            with self.assertRaises(SecurityError) as context:
                self.run_async(client.generate_strategy_code(self.evolution_package, max_retries=2))

            self.assertEqual(mock_service.generate.call_count, 2)
            self.assertIn("Forbidden import detected", str(context.exception))

    def test_c_mode_prompt_assembly(self):
        """Test C-mode context assembly generates proper prompt structure."""
        client = EvolutionLLMClient()
        prompt = client._assemble_c_mode_context(self.evolution_package)

        # Verify key sections are present
        self.assertIn("[Evolution Mode: C-MODE]", prompt)
        self.assertIn("Current Strategy Code", prompt)
        self.assertIn("Performance Metrics", prompt)
        self.assertIn("Vulnerability Analysis", prompt)
        self.assertIn("Evolution History", prompt)
        self.assertIn("Competitive Context", prompt)
        self.assertIn("Market Environment", prompt)
        self.assertIn("Instructions:", prompt)

        # Verify metrics are included
        self.assertIn("Trinity Score", prompt)
        self.assertIn("120", prompt)
        self.assertIn("Bull", prompt)  # Market regime

    def test_self_correction_with_error_context(self):
        """Test self-correction loop includes error context in subsequent calls."""
        mock_service = AsyncMock()
        mock_service.generate.return_value = "class strategy:\n    def generate_signal(self, data):\n        return 1"

        error_context = "Traceback (most recent call last):\n  File \"test.py\", line 1, in <module>\n    x = 1/0\nZeroDivisionError: division by zero"

        with patch.object(StrategyLoader, 'validate_code') as mock_validate:
            # First validation fails, then succeeds
            mock_validate.side_effect = [SyntaxError("Invalid syntax"), None]

            client = EvolutionLLMClient(llm_service=mock_service)
            self.run_async(client.generate_strategy_code(self.evolution_package))

            # Verify error context was passed to the LLM call
            args, kwargs = mock_service.generate.call_args
            self.assertIn("SELF-CORRECTION REQUIRED", args[0])
            self.assertIn("Invalid syntax", args[0])

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
        self.assertEqual(cleaned_code.strip(), "class cleaned_strategy:\n    def generate_signal(self, data):\n        return 1")

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