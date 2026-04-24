import os
import logging
import asyncio
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
import litellm
from litellm import acompletion, completion_cost

logger = logging.getLogger(__name__)

@dataclass
class LLMResponse:
    """Structured response from LLMService"""
    content: str
    model: str
    cost: float
    tokens_prompt: int
    tokens_completion: int
    attempts: int
    fallback_triggered: bool = False

class LLMServiceError(Exception):
    """Base exception for LLMService"""
    pass

class LLMService:
    """
    Professional LLM orchestration layer using LiteLLM.
    Provides dynamic model routing, async execution, fallback mechanisms, and cost tracking.
    """

    def __init__(self):
        # Model routing map: Logical Name -> Actual Model ID
        # Can be overridden by environment variables: LLM_ROUTE_DEFAULT, etc.
        self.model_routing = {
            "default": os.getenv("LLM_ROUTE_DEFAULT", "gpt-4o-mini"),
            "fast": os.getenv("LLM_ROUTE_FAST", "gpt-4o-mini"),
            "creative": os.getenv("LLM_ROUTE_CREATIVE", "claude-3-5-sonnet-20240620"),
            "strong": os.getenv("LLM_ROUTE_STRONG", "gpt-4o"),
        }

        # Global timeout settings
        try:
            raw_timeout = float(os.getenv("LLM_TIMEOUT", "0"))
        except ValueError:
            raw_timeout = 0.0
        self.timeout = None if raw_timeout <= 0 else max(1.0, raw_timeout)
        self.max_retries = int(os.getenv("LLM_MAX_RETRIES", "2"))
        self.retry_backoff = float(os.getenv("LLM_RETRY_BACKOFF", "2.0"))

    def get_model_id(self, model_type: str) -> str:
        """Map logical model type to actual model ID"""
        return self.model_routing.get(model_type, self.model_routing["default"])

    async def generate(
        self,
        prompt: str,
        model_type: str = "default",
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate text using the specified model type.

        Args:
            prompt: The input prompt
            model_type: Logical model type ('default', 'fast', 'creative', 'strong')
            temperature: Sampling temperature
            max_tokens: Maximum tokens for completion
            **kwargs: Additional arguments passed to litellm.acompletion
        """
        model_id = self.get_model_id(model_type)
        return await self.generate_with_fallback(
            prompt=prompt,
            primary_model=model_id,
            fallback_models=[self.model_routing["default"]] if model_id != self.model_routing["default"] else [],
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )

    async def generate_with_fallback(
        self,
        prompt: str,
        primary_model: str,
        fallback_models: List[str],
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Try to generate content using the primary model, then fallback sequentially.
        """
        all_models = [primary_model] + fallback_models
        last_exception = None

        for attempt_idx, model_id in enumerate(all_models):
            attempts_for_this_model = 0

            for retry in range(self.max_retries + 1):
                attempts_for_this_model += 1
                try:
                    # Prepare messages for chat completion
                    messages = [{"role": "user", "content": prompt}]
                    request_kwargs = dict(
                        model=model_id,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        **kwargs
                    )
                    if self.timeout is not None:
                        request_kwargs["timeout"] = self.timeout
                    response = await acompletion(**request_kwargs)

                    content = response.choices[0].message.content
                    if not content:
                        raise LLMServiceError("LLM returned empty content")

                    # Calculate cost
                    cost = completion_cost(completion_response=response)

                    return LLMResponse(
                        content=content.strip(),
                        model=model_id,
                        cost=cost,
                        tokens_prompt=response.get("usage", {}).get("prompt_tokens", 0),
                        tokens_completion=response.get("usage", {}).get("completion_tokens", 0),
                        attempts=attempts_for_this_model,
                        fallback_triggered=(attempt_idx > 0)
                    )

                except Exception as e:
                    last_exception = e
                    logger.warning(
                        f"LLM request failed for model {model_id} (attempt {retry+1}/{self.max_retries+1}): {str(e)}"
                    )

                    if retry < self.max_retries:
                        await asyncio.sleep(self.retry_backoff * (retry + 1))
                    else:
                        # Move to next model in fallback list
                        break

        logger.error(f"All LLM models failed. Last error: {last_exception}")
        raise LLMServiceError(f"LLM Generation failed after trying all models: {str(last_exception)}")

# Singleton instance for easy access
_llm_service_instance: Optional[LLMService] = None

def get_llm_service() -> LLMService:
    """Get or create the singleton LLMService instance"""
    global _llm_service_instance
    if _llm_service_instance is None:
        _llm_service_instance = LLMService()
    return _llm_service_instance
