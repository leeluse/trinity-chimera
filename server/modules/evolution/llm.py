import logging
import os
import traceback
import asyncio
from typing import Dict, Any, Optional
from server.shared.llm.llm_client import build_default_llm_service, LLMUnavailableError
from server.shared.market.strategy_loader import StrategyLoader, SecurityError

logger = logging.getLogger(__name__)

class EvolutionLLM:
    """전략 진화(Evolution)를 위한 LLM 인터페이스 및 브레인 로직"""

    def __init__(self):
        # 기존 서비스 빌더 활용 (나중에 shared/llm으로 이동 가능)
        self.llm_service = build_default_llm_service()

    # -------------------------------------------------------------------------
    # 전략 코드 생성: C-MODE 컨텍스트를 조립하고 LLM에게 개선된 코드 요청
    # -------------------------------------------------------------------------
    async def generate_improved_code(
        self,
        evolution_package: Dict[str, Any],
        max_retries: int = 3
    ) -> str:
        if not self.llm_service:
            raise LLMUnavailableError("LLM 서비스가 설정되지 않았습니다.")

        # 1. 진화 모드 선택 (Mode 1: 튜닝 / Mode 2: 신규 생성)
        mode = self._select_evolution_mode(evolution_package)
        label = evolution_package.get('agent_id', 'unknown')
        logger.info(f"[{label}] Evolution mode: {mode}")

        # 2. 프롬프트 조립
        prompt = self._assemble_prompt(evolution_package, mode)
        
        # 3. 생성 및 자가 보정(Self-Correction) 루프
        attempt = 0
        last_error = None

        while attempt < max_retries:
            try:
                # 에러가 있었다면 프롬프트에 추가
                final_prompt = prompt
                if last_error:
                    final_prompt += f"\n\n### 이전 시도 실패 사유:\n{last_error}\n위 에러를 해결해서 다시 코드를 짜줘."

                raw_response = await self.llm_service.generate(final_prompt)
                code = self._clean_code(raw_response)
                
                # 정적 보안/문법 검증
                StrategyLoader.validate_code(code)
                return code

            except (SecurityError, SyntaxError) as e:
                attempt += 1
                last_error = traceback.format_exc()
                logger.warning(f"[{label}] 코드 검증 실패 (시도 {attempt}/{max_retries}): {e}")
                if attempt >= max_retries: raise e
            except Exception as e:
                logger.error(f"[{label}] LLM 생성 중 예외 발생: {e}")
                raise e

    # -------------------------------------------------------------------------
    # 진화 모드 결정: 시장 상황(Regime)과 현재 성과를 바탕으로 전략 수정 강도 결정
    # -------------------------------------------------------------------------
    def _select_evolution_mode(self, pkg: Dict[str, Any]) -> str:
        metrics = pkg.get("metrics", {})
        score = float(metrics.get("trinity_score") or 0.0)
        
        # 성과가 너무 낮거나( < 50), 너무 높아서 정체기인 경우 자유 생성(Free Generation) 모드로 전환
        if score < 50 or score > 85:
            return "free_generation"
        return "parameter_tuning"

    # -------------------------------------------------------------------------
    # 프롬프트 조립: 에이전트 특성과 현재 코드, 마켓 데이터를 융합한 컨텍스트 생성
    # -------------------------------------------------------------------------
    def _assemble_prompt(self, pkg: Dict[str, Any], mode: str) -> str:
        current_code = pkg.get("current_strategy_code", "")
        metrics = pkg.get("metrics", {})
        
        mode_instruction = (
            "기존 파라미터만 조정해라." if mode == "parameter_tuning" 
            else "완전히 새로운 지표와 구조를 도입해서 코드를 다시 짜라."
        )

        return f"""
### [Trinity Strategy Evolution]
지시사항: 현재 전략의 성과를 분석하고 최신 시장 상황에 맞춰 개선해라.
수정 모드: {mode} ({mode_instruction})

#### 1. 현재 포트폴리오 성과
- Trinity Score: {metrics.get('trinity_score', 0):.2f}
- 수익률: {metrics.get('return', 0):.4f}
- MDD: {metrics.get('mdd', 0):.4f}

#### 2. 현재 코드
```python
{current_code}
```

반드시 `CustomStrategy` 클래스로 구현하고, 결과를 설명 없이 오직 ```python ``` 블록만 출력해라.
"""

    # -------------------------------------------------------------------------
    # 코드 정제: LLM 응답에서 마크다운 블록을 제거하고 순수 파이썬 코드만 보존
    # -------------------------------------------------------------------------
    def _clean_code(self, text: str) -> str:
        if "```python" in text:
            return text.split("```python")[1].split("```")[0].strip()
        return text.strip()
