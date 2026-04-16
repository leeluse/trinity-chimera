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
        evolution_package["_selected_mode"] = mode
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
        memory_context = pkg.get("memory_context") or {}
        attempt = int(pkg.get("attempt", 1) or 1)
        last_reason = str(pkg.get("last_reason") or "").strip()
        blocked_fingerprints = pkg.get("blocked_fingerprints") or []
        hard_gates = memory_context.get("hard_gates") or {}
        recent_failures = memory_context.get("recent_failures") or []
        recent_successes = memory_context.get("recent_successes") or []
        
        mode_instruction = (
            "기존 파라미터만 조정해라." if mode == "parameter_tuning" 
            else "완전히 새로운 지표와 구조를 도입해서 코드를 다시 짜라."
        )

        fail_lines = []
        for row in recent_failures[:5]:
            reason = str(row.get("reason") or "unknown").strip()
            fail_lines.append(f"- {reason}")
        failure_block = "\n".join(fail_lines) if fail_lines else "- (최근 실패 이력 없음)"

        success_lines = []
        for row in recent_successes[:3]:
            m = row.get("metrics") or {}
            success_lines.append(
                f"- win={float(m.get('win_rate', 0.0)):.3f}, pf={float(m.get('profit_factor', 0.0)):.3f}, "
                f"ret={float(m.get('total_return', 0.0)):.3f}, mdd={float(m.get('max_drawdown', 0.0)):.3f}, "
                f"trades={int(m.get('total_trades', 0))}"
            )
        success_block = "\n".join(success_lines) if success_lines else "- (최근 성공 이력 없음)"

        blocked_lines = []
        for fp in blocked_fingerprints[:8]:
            text = str(fp).strip()
            if not text:
                continue
            blocked_lines.append(f"- {text[:12]}")
        blocked_block = "\n".join(blocked_lines) if blocked_lines else "- (이번 사이클 중 차단된 fingerprint 없음)"
        last_reason_block = last_reason if last_reason else "(직전 실패 사유 없음)"

        return f"""
### [Trinity Strategy Evolution]
지시사항: 현재 전략의 성과를 분석하고 최신 시장 상황에 맞춰 개선해라.
수정 모드: {mode} ({mode_instruction})
시도 번호: {attempt}

#### 1. 현재 포트폴리오 성과
- Trinity Score: {metrics.get('trinity_score', 0):.2f}
- 수익률: {metrics.get('return', 0):.4f}
- MDD: {metrics.get('mdd', 0):.4f}

#### 2.5. 하드 게이트 (절대 미충족 금지)
- min_win_rate: {hard_gates.get('min_win_rate', 0.0)}
- min_profit_factor: {hard_gates.get('min_profit_factor', 0.0)}
- min_total_return: {hard_gates.get('min_total_return', 0.0)}
- max_drawdown(abs): {hard_gates.get('max_drawdown', 1.0)}
- min_total_trades: {hard_gates.get('min_total_trades', 0)}
- min_sharpe_ratio: {hard_gates.get('min_sharpe_ratio', 0.0)}

#### 2.6. 최근 실패 패턴 (반드시 회피)
{failure_block}

#### 2.7. 최근 성공 패턴 (참고)
{success_block}

#### 2.8. 이번 사이클 즉시 피드백 (강제 반영)
- 직전 실패 사유: {last_reason_block}
- 차단된 후보 fingerprint:
{blocked_block}

#### 3. 현재 코드
```python
{current_code}
```

#### 4. 호환성 필수 규칙 (미준수 시 즉시 폐기)
1) `from server.shared.market.strategy_interface import StrategyInterface` 를 절대 사용하지 마라.
2) 클래스 이름은 정확히 `CustomStrategy` 여야 하며, 반드시 `class CustomStrategy(Strategy):` 형태여야 한다.
3) 메서드는 반드시 `def generate_signals(self, data, params):` 를 구현해야 한다.
4) 반환은 반드시 `Signal(...)` 객체여야 한다. (정수/문자열 단독 반환 금지)
5) 이번 결과는 위의 차단 fingerprint들과 AST 기준으로 실질적으로 달라야 한다. 지표/조건/파라미터를 최소 2개 이상 변경해라.
6) 결과는 설명 없이 오직 하나의 ```python 코드 블록```만 출력해라.

#### 5. 출력 템플릿 (형식 강제)
```python
class CustomStrategy(Strategy):
    name = "CustomStrategy"
    params = {{}}

    def generate_signals(self, data, params):
        # data: pandas DataFrame with open/high/low/close/volume
        # return Signal(entry=..., exit=..., direction="long"|"short")
        ...
```
"""

    # -------------------------------------------------------------------------
    # 코드 정제: LLM 응답에서 마크다운 블록을 제거하고 순수 파이썬 코드만 보존
    # -------------------------------------------------------------------------
    def _clean_code(self, text: str) -> str:
        if "```python" in text:
            return text.split("```python")[1].split("```")[0].strip()
        return text.strip()
