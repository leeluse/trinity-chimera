"""
LLM Feedback Client - T-003, T-004 구현

MetricsBuffer 트리거 수신 시:
- 컨텍스트 구성 (현재 전략 + 성과 추이 + 실패 이력)
- LLM 호출 -> 수정된 전략 수신
- AST 검증 통과 시 즉시 배포
- 점수 개선 없어도 다음 누적 후 재시도
- LLM 실패 시 명시적 오류 처리 (silent fail 없음)
"""

import logging
import os
import time
import traceback
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

import anthropic
from anthropic.types import Message

from server.ai_trading.core.strategy_loader import StrategyLoader, SecurityError
from server.api.services.supabase_client import SupabaseManager

logger = logging.getLogger(__name__)


class LLMUnavailableError(Exception):
    """LLM 서비스 사용 불가 예외"""
    pass


class StrategyValidationError(Exception):
    """전략 코드 검증 실패 예외"""
    pass


class EvolutionMode(Enum):
    """진화 모드"""
    PARAMETER_TUNING = "parameter_tuning"  # 모드 1: 파라미터 조정
    FREE_GENERATION = "free_generation"   # 모드 2: 전략 구조 자유 생성


@dataclass
class EvolutionContext:
    """LLM 피드백에 사용되는 컨텍스트"""
    agent_id: str
    current_strategy_code: str
    metrics_summary: Dict[str, Any]
    failed_reasons: List[str]
    evolution_count: int
    market_regime: str = "unknown"
    competitive_rank: str = "unknown"


class LLMFeedbackClient:
    """
    MetricsBuffer 트리거 응답 및 전략 진화 관리

    T-003: 자동 피드백 + 전략 배포
    T-004: LLM 실패 시 명시적 오류 처리
    T-007: 진화 모드 자동 선택
    """

    def __init__(self):
        self.supabase = SupabaseManager()
        self._anthropic_client: Optional[anthropic.Anthropic] = None
        self._init_llm_client()
        self._evolution_counts: Dict[str, int] = {}
        self._last_failure_reasons: Dict[str, List[str]] = {}

    def _init_llm_client(self) -> None:
        """Anthropic 클라이언트 초기화 - 실패 시 예외"""
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.error("ANTHROPIC_API_KEY not set in environment")
            raise LLMUnavailableError("ANTHROPIC_API_KEY not configured")

        try:
            self._anthropic_client = anthropic.Anthropic(api_key=api_key)
            logger.info("Anthropic client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic client: {e}")
            raise LLMUnavailableError(f"LLM client initialization failed: {e}")

    def _determine_evolution_mode(self, agent_id: str, trinity_score: float) -> EvolutionMode:
        """
        T-007: 진화 모드 자동 선택

        - 진화 횟수 < 3 또는 Trinity Score > 70: 파라미터 튜닝
        - 그 외: 자유 생성
        """
        count = self._evolution_counts.get(agent_id, 0)

        if count < 3 or trinity_score > 70:
            return EvolutionMode.PARAMETER_TUNING
        return EvolutionMode.FREE_GENERATION

    async def process_metrics_trigger(
        self,
        agent_id: str,
        metrics_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        MetricsBuffer 트리거 발생 시 전략 진화 실행

        Args:
            agent_id: 에이전트 ID
            metrics_context: MetricsBuffer에서 전달된 컨텍스트

        Returns:
            진화 결과 딕셔너리
        """
        result = {
            "agent_id": agent_id,
            "status": "started",
            "timestamp": time.time(),
            "new_strategy_id": None,
            "error": None,
        }

        try:
            # 1. 현재 전략 코드 가져오기
            strategy_data = await self.supabase.get_agent_strategy(agent_id)
            if not strategy_data:
                raise ValueError(f"No strategy found for agent {agent_id}")

            current_code = strategy_data.get("code", "")
            current_score = metrics_context.get("avg_trinity_score", 0)

            # 2. 진화 모드 결정
            evolution_mode = self._determine_evolution_mode(agent_id, current_score)
            result["evolution_mode"] = evolution_mode.value

            # 3. 컨텍스트 구성
            context = EvolutionContext(
                agent_id=agent_id,
                current_strategy_code=current_code,
                metrics_summary=metrics_context,
                failed_reasons=metrics_context.get("failed_reasons", []),
                evolution_count=self._evolution_counts.get(agent_id, 0),
                market_regime=metrics_context.get("market_regime", "unknown"),
                competitive_rank=metrics_context.get("competitive_rank", "unknown"),
            )

            # 4. LLM 호출 - 수정된 전략 코드 수신
            new_code = await self._call_llm_for_strategy(context, evolution_mode)

            # 5. AST 검증
            try:
                StrategyLoader.validate_code(new_code)
            except SecurityError as e:
                raise StrategyValidationError(f"Security validation failed: {e}")
            except SyntaxError as e:
                raise StrategyValidationError(f"Syntax validation failed: {e}")

            # 6. 새 전략 저장
            prev_strategy_id = strategy_data.get("id")
            new_strategy_id = await self.supabase.save_strategy(
                agent_id=agent_id,
                code=new_code,
                rationale=f"Automated evolution via {evolution_mode.value} mode",
                params=strategy_data.get("params", {}),
            )

            if not new_strategy_id:
                raise ValueError("Failed to save new strategy")

            # 7. 진화 카운트 증가
            self._evolution_counts[agent_id] = self._evolution_counts.get(agent_id, 0) + 1

            # 8. 성공 로깅
            await self.supabase.save_improvement_log(
                agent_id=agent_id,
                prev_id=prev_strategy_id,
                new_id=new_strategy_id,
                analysis=f"{evolution_mode.value} evolution completed",
                expected={"mode": evolution_mode.value},
            )

            result.update({
                "status": "success",
                "new_strategy_id": new_strategy_id,
                "evolution_mode": evolution_mode.value,
            })

            logger.info(
                f"Evolution successful for {agent_id}: "
                f"mode={evolution_mode.value}, new_id={new_strategy_id}"
            )

        except LLMUnavailableError as e:
            # T-004: 명시적 오류 처리 - silent fail 없음
            error_msg = f"LLM unavailable: {e}"
            logger.error(error_msg)
            result["status"] = "failed"
            result["error"] = error_msg
            result["error_type"] = "LLM_UNAVAILABLE"

            # Supabase에 실패 기록
            await self._record_failure(agent_id, error_msg)

        except StrategyValidationError as e:
            error_msg = f"Strategy validation failed: {e}"
            logger.error(error_msg)
            result["status"] = "failed"
            result["error"] = error_msg
            result["error_type"] = "VALIDATION_FAILED"

            # 실패 사유 저장 (다음 누적 시 활용)
            self._add_failure_reason(agent_id, error_msg)

        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            logger.exception(error_msg)
            result["status"] = "failed"
            result["error"] = error_msg
            result["error_type"] = "UNKNOWN"

        return result

    async def _call_llm_for_strategy(
        self,
        context: EvolutionContext,
        mode: EvolutionMode
    ) -> str:
        """
        LLM 호출로 수정된 전략 코드 생성

        Args:
            context: 진화 컨텍스트
            mode: 진화 모드

        Returns:
            생성된 전략 코드 문자열

        Raises:
            LLMUnavailableError: LLM 호출 실패 시
        """
        if not self._anthropic_client:
            raise LLMUnavailableError("LLM client not initialized")

        prompt = self._build_prompt(context, mode)

        try:
            start_time = time.time()

            message: Message = self._anthropic_client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=4000,
                temperature=0.3,
                system=self._get_system_prompt(mode),
                messages=[{"role": "user", "content": prompt}]
            )

            duration = time.time() - start_time
            logger.info(f"LLM call completed in {duration:.2f}s")

            if not message.content or len(message.content) == 0:
                raise LLMUnavailableError("LLM returned empty response")

            generated_code = self._extract_code_from_response(
                message.content[0].text if hasattr(message.content[0], 'text') else str(message.content)
            )

            if not generated_code:
                raise LLMUnavailableError("Could not extract code from LLM response")

            return generated_code

        except anthropic.APIError as e:
            raise LLMUnavailableError(f"Anthropic API error: {e}")
        except Exception as e:
            raise LLMUnavailableError(f"LLM call failed: {e}")

    def _build_prompt(self, ctx: EvolutionContext, mode: EvolutionMode) -> str:
        """LLM 프롬프트 구성"""
        metrics = ctx.metrics_summary

        prompt = f"""### Evolution Request
Agent: {ctx.agent_id}
Mode: {mode.value}
Evolution Count: {ctx.evolution_count}

### Current Strategy Code
```python
{ctx.current_strategy_code}
```

### Performance Metrics (Averaged from {metrics.get('tick_count', 0)} ticks)
- Trinity Score: {metrics.get('avg_trinity_score', 'N/A'):.2f}
- Trend: {'+' if metrics.get('score_trend', 0) > 0 else ''}{metrics.get('score_trend', 0):.2f}
- Average Return: {metrics.get('avg_return', 'N/A'):.4f}
- Average Sharpe: {metrics.get('avg_sharpe', 'N/A'):.2f}
- Trigger Reason: {metrics.get('trigger_reason', 'N/A')}

### Previous Failures (if any)
{chr(10).join(f"- {r}" for r in ctx.failed_reasons) if ctx.failed_reasons else "None"}

### Instructions
"""
        if mode == EvolutionMode.PARAMETER_TUNING:
            prompt += """Improve this strategy by adjusting parameters.
- Keep the core logic structure
- Optimize thresholds, periods, multipliers
- Avoid changing the class name"""
        else:
            prompt += """Generate an improved strategy with potentially new structure.
- May introduce new indicators or logic patterns
- Consider different signal generation approaches
- Maintain StrategyInterface compliance"""

        prompt += """

### Output Requirements
1. Provide ONLY valid Python code
2. Class must implement StrategyInterface
3. Include '# Generated by Trinity AI' comment
4. No external imports beyond pandas, numpy
5. No forbidden functions (os, sys, subprocess, etc.)"""

        return prompt

    def _get_system_prompt(self, mode: EvolutionMode) -> str:
        """시스템 프롬프트 반환"""
        return """You are an expert quantitative strategy evolver. Your task is to improve trading strategies.

Requirements:
- Output ONLY Python code, no explanations outside code blocks
- Code must be valid and syntactically correct
- Strategy class must implement StrategyInterface with generate_signal() method
- Avoid forbidden modules: os, sys, subprocess, shutil, socket, requests, urllib
- Include proper error handling"""

    def _extract_code_from_response(self, response: str) -> str:
        """LLM 응답에서 코드 블록 추출"""
        # Try different code block formats
        for delimiter in ["```python", "```"]:
            if delimiter in response:
                parts = response.split(delimiter)
                if len(parts) >= 2:
                    code = parts[1].split("```")[0] if "```" in parts[1] else parts[1]
                    return code.strip()

        # If no code blocks found, return cleaned response
        return response.strip()

    def _add_failure_reason(self, agent_id: str, reason: str) -> None:
        """실패 사유 저장 (다음 누적 시 활용)"""
        if agent_id not in self._last_failure_reasons:
            self._last_failure_reasons[agent_id] = []
        self._last_failure_reasons[agent_id].append(f"{datetime.now().isoformat()}: {reason}")
        # 최근 5개만 유지
        self._last_failure_reasons[agent_id] = self._last_failure_reasons[agent_id][-5:]

    async def _record_failure(self, agent_id: str, error_msg: str) -> None:
        """Supabase에 실패 기록"""
        try:
            # evolution_failed 상태 기록
                await self.supabase.save_improvement_log(
                agent_id=agent_id,
                prev_id=None,
                new_id=None,
                analysis=f"FAILED: {error_msg}",
                expected={},
            )
        except Exception as e:
            logger.error(f"Failed to record failure to Supabase: {e}")


# Global singleton instance
_llm_feedback_client: Optional[LLMFeedbackClient] = None


def get_llm_feedback_client() -> LLMFeedbackClient:
    """전역 LLMFeedbackClient 인스턴스 반환"""
    global _llm_feedback_client
    if _llm_feedback_client is None:
        _llm_feedback_client = LLMFeedbackClient()
    return _llm_feedback_client
