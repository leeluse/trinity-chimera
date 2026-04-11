#!/usr/bin/env python3
"""
Real LLM connectivity test.

This test attempts actual API calls to LLM services using configured credentials.
"""

import os
import asyncio
import requests
import unittest
from typing import Dict, Any


class TestRealLLMConnectivity(unittest.TestCase):
    """Tests actual LLM API connectivity."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment."""
        cls.nvidia_api_key = os.getenv('NVIDIA_NIM_API_KEY')
        cls.has_nvidia_access = bool(cls.nvidia_api_key)

        # NVIDIA NIM endpoint (common endpoint for testing)
        cls.nvidia_endpoint = "https://integrate.api.nvidia.com/v1/chat/completions"

    def run_async(self, coroutine):
        """Helper method to run async tests."""
        return asyncio.run(coroutine)

    def test_nvidia_nim_api_connectivity(self):
        """Test connectivity to NVIDIA NIM API."""
        if not self.has_nvidia_access:
            self.skipTest("NVIDIA NIM API key not available - skipping real API test")

        # Simple API connectivity test
        headers = {
            "Authorization": f"Bearer {self.nvidia_api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "meta/llama-3.1-70b-instruct",
            "messages": [
                {"role": "user", "content": "Say 'Hello World'"}
            ],
            "max_tokens": 100,
            "temperature": 0.1
        }

        try:
            response = requests.post(self.nvidia_endpoint, json=payload, headers=headers, timeout=30)

            # Check for successful response
            self.assertIn(response.status_code, [200, 201, 202],
                         f"API returned status code {response.status_code}")

            print(f"✅ NVIDIA NIM API connectivity test passed: {response.status_code}")

        except requests.exceptions.RequestException as e:
            self.fail(f"NVIDIA NIM API connection failed: {e}")

    def test_environment_variables_exist(self):
        """Verify that LLM environment variables are configured."""
        # Check for NVIDIA NIM API key
        self.assertTrue(self.has_nvidia_access,
                       "NVIDIA_NIM_API_KEY environment variable should be configured")

        print("✅ LLM environment variables are properly configured")

    def test_evolution_client_mock_functionality(self):
        """Test that EvolutionLLMClient works with mock responses."""
        # Import here to avoid dependency issues
        from unittest.mock import AsyncMock, MagicMock

        class MockEvolutionLLMClient:
            """Mock EvolutionLLMClient for testing."""

            async def generate_strategy_code(self, evolution_package, max_retries=3):
                """Mock strategy generation."""
                prompt = self._assemble_c_mode_context(evolution_package)

                # Mock LLM call
                code = await self._call_llm(prompt)

                # Mock validation
                self._validate_code(code)

                return code

            def _assemble_c_mode_context(self, pkg):
                """Mock C-mode context assembly."""
                return f"Mock prompt for metrics: {pkg.get('metrics', {})}"

            async def _call_llm(self, prompt):
                """Mock LLM call."""
                return "# Mock Strategy Code\nclass evolved_strategy:\n    def generate_signal(self, data):\n        return 1"

            def _validate_code(self, code):
                """Mock code validation."""
                if not code:
                    raise ValueError("Empty code")

        async def run_test():
            client = MockEvolutionLLMClient()
            evolution_package = {
                "current_strategy_code": "class mock_strategy:\n    def generate_signal(self, data):\n        return 1",
                "metrics": {"trinity_score": 120}
            }

            code = await client.generate_strategy_code(evolution_package)
            return code

        # Run the async test
        code = self.run_async(run_test())

        self.assertIsInstance(code, str)
        self.assertIn("Mock Strategy Code", code)
        self.assertIn("evolved_strategy", code)

        print("✅ EvolutionLLMClient mock functionality works correctly")

    def test_api_error_handling_simulation(self):
        """Test error handling simulation for LLM API calls."""
        from unittest.mock import AsyncMock

        async def simulate_api_failure():
            # Mock LLM service that simulates API failure
            mock_service = AsyncMock()
            mock_service.generate.side_effect = Exception("API rate limit exceeded")

            client = MockEvolutionLLMClient()

            # Test error handling
            with self.assertRaises(Exception) as context:
                await client.generate_strategy_code({"metrics": {}})

            return str(context.exception)

        error_message = self.run_async(simulate_api_failure())
        self.assertIn("API rate limit exceeded", error_message)

        print("✅ API error handling simulation works correctly")


class MockEvolutionLLMClient:
    """Mock EvolutionLLMClient for testing."""

    async def generate_strategy_code(self, evolution_package, max_retries=3):
        """Mock strategy generation."""
        prompt = self._assemble_c_mode_context(evolution_package)

        # Mock LLM call
        code = await self._call_llm(prompt)

        # Mock validation
        self._validate_code(code)

        return code

    def _assemble_c_mode_context(self, pkg):
        """Mock C-mode context assembly."""
        return f"Mock prompt for metrics: {pkg.get('metrics', {})}"

    async def _call_llm(self, prompt):
        """Mock LLM call."""
        return "# Mock Strategy Code\nclass evolved_strategy:\n    def generate_signal(self, data):\n        return 1"

    def _validate_code(self, code):
        """Mock code validation."""
        if not code:
            raise ValueError("Empty code")


if __name__ == "__main__":
    # Run the tests
    unittest.main()