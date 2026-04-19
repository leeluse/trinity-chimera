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
        forced_mode = str(os.getenv("EVOLUTION_FORCE_MODE") or "").strip().lower()
        if forced_mode in {"mode1", "1", "parameter_tuning", "parameter-tuning", "tuning"}:
            return "parameter_tuning"
        if forced_mode in {"mode2", "2", "free_generation", "free-generation", "free"}:
            return "free_generation"

        # L1/L2 트리거 = HIGH intensity → 완전 신규 전략 생성
        trigger_level = str(pkg.get("trigger_level") or "L4").strip().upper()
        if trigger_level in {"L1", "L2"}:
            return "free_generation"

        metrics = pkg.get("metrics", {})
        score = float(metrics.get("trinity_score") or 0.0)

        # Trinity Score 0-100 기준:
        # < 30: 전략이 너무 나쁨 → 완전 재설계
        # > 70: 고성능 정체 → 다양성 탐색
        # 30-70: 점진적 개선
        if score < 30 or score > 70:
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
        failure_summary = memory_context.get("failure_summary") or []
        best_accepted = memory_context.get("best_accepted") or {}
        unexplored_mutations = memory_context.get("unexplored_mutations") or []
        next_mutation = str(memory_context.get("next_mutation") or "").strip()
        
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

        summary_lines = []
        for row in failure_summary[:6]:
            tag = str(row.get("tag") or "other").strip()
            cnt = int(row.get("count") or 0)
            summary_lines.append(f"- {tag}: {cnt}")
        failure_summary_block = "\n".join(summary_lines) if summary_lines else "- (태그 집계 없음)"

        best_metrics = best_accepted.get("metrics") if isinstance(best_accepted, dict) else {}
        if isinstance(best_metrics, dict) and best_metrics:
            best_block = (
                f"- strategy_id={best_accepted.get('strategy_id') or '-'}, "
                f"pf={float(best_metrics.get('profit_factor', 0.0)):.3f}, "
                f"win={float(best_metrics.get('win_rate', 0.0)):.3f}, "
                f"ret={float(best_metrics.get('total_return', 0.0)):.3f}, "
                f"mdd={float(best_metrics.get('max_drawdown', 0.0)):.3f}, "
                f"trades={int(best_metrics.get('total_trades', 0))}"
            )
        else:
            best_block = "- (아직 채택된 전략 없음)"

        unexplored_lines = []
        for item in unexplored_mutations[:6]:
            text = str(item).strip()
            if text:
                unexplored_lines.append(f"- {text}")
        unexplored_block = "\n".join(unexplored_lines) if unexplored_lines else "- (미탐색 방향 정보 없음)"
        next_mutation_block = next_mutation or "structural_novelty"

        return f"""
### [Trinity Strategy Evolution: High-Performance Quant Mode]
지시사항: 당신은 세계 최고의 퀀트 트레이더이자 알고리즘 개발자입니다.
제시된 현재 전략의 성과를 기반으로, 승률·리스크 대비 수익비(RR)가 극대화된 차세대 전략을 설계하십시오.

[반드시 준수할 분석 프로세스]
1. (Critical Analysis) <think> 태그 내에서 현재 전략의 코드와 성과를 철저히 비판하십시오.
2. (Market Hypothesis) 현재 시장 국면에 가장 적합한 새로운 가설을 설정하십시오.
3. (Systemic Improvement) 지표 간의 시너지를 고려한 새로운 진입/청산 로직을 설계하십시오.
수정 모드: {mode} ({mode_instruction})
시도 번호: {attempt}

#### 1. 현재 포트폴리오 성과
- Trinity Score: {metrics.get('trinity_score', 0):.2f}
- 수익률: {metrics.get('return', 0):.4f}
- MDD: {metrics.get('mdd', 0):.4f}

#### 2. 하드 게이트 (절대 미충족 금지)
- min_win_rate: {hard_gates.get('min_win_rate', 0.0)}
- min_profit_factor: {hard_gates.get('min_profit_factor', 0.0)}
- min_total_return: {hard_gates.get('min_total_return', 0.0)}
- max_drawdown(abs): {hard_gates.get('max_drawdown', 1.0)}
- min_total_trades: {hard_gates.get('min_total_trades', 0)}
- min_sharpe_ratio: {hard_gates.get('min_sharpe_ratio', 0.0)}

#### 3. 최근 실패 패턴 (반드시 회피)
{failure_block}

#### 4. 최근 성공 패턴 (참고)
{success_block}

#### 5. 이번 사이클 즉시 피드백
- 직전 실패 사유: {last_reason_block}
- 차단된 후보 fingerprint:
{blocked_block}

#### 6. 실패 이유 태그 집계
{failure_summary_block}

#### 7. 지금까지 최고 성능 전략 (기준점)
{best_block}

#### 8. 아직 덜 시도한 탐색 방향
{unexplored_block}

#### 9. 이번 시도에서 반드시 우선할 방향
- next_mutation: {next_mutation_block}

#### 10. 현재 코드 (참고/개선 대상)
```python
{current_code}
```

#### 11. 출력 규격 (반드시 이 형식으로만 출력)

**함수 시그니처 (변경 불가):**
```python
def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:
```
- `train_df` / `test_df`: DatetimeIndex, 컬럼 = open / high / low / close / volume
- 반환: `test_df.index`와 동일한 인덱스의 `pd.Series` (값: 1=롱, -1=숏, 0=관망)
- import는 `numpy as np`, `pandas as pd`만 사용 가능

**거래 수 경고:** 진입 조건이 지나치게 엄격하면 신호가 0건이 되어 즉시 폐기된다.
테스트 기간(수백~수천 행) 중 **최소 30건 이상** 신호가 발생하도록 설계해라.

**지표 구현 레시피 (numpy/pandas 전용):**
```
# EMA
ema = close.ewm(span=n, adjust=False).mean()
# RSI
d = close.diff(); g = d.clip(lower=0).rolling(14).mean(); l = -d.clip(upper=0).rolling(14).mean()
rsi = 100 - 100 / (1 + g / l.replace(0, 1e-9))
# Bollinger Bands
sma = close.rolling(20).mean(); std = close.rolling(20).std()
upper = sma + 2*std; lower = sma - 2*std
# ATR
tr = pd.concat([(high-low), (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
atr = tr.ewm(span=14, adjust=False).mean()
# MACD
macd = close.ewm(span=12,adjust=False).mean() - close.ewm(span=26,adjust=False).mean()
signal_line = macd.ewm(span=9,adjust=False).mean()
```

**이번 결과는 차단된 fingerprint들과 AST 기준으로 실질적으로 달라야 한다.
지표/조건/파라미터를 최소 2개 이상 변경해라.**

모든 추론은 `<think>` 태그 안에, 최종 코드 블록 하나만 마지막에 출력해라.

**출력 템플릿:**
```python
import numpy as np
import pandas as pd

def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:
    close = test_df['close']
    high  = test_df['high']
    low   = test_df['low']
    vol   = test_df['volume']

    # --- 지표 계산 ---
    ema_fast = close.ewm(span=12, adjust=False).mean()
    ema_slow = close.ewm(span=26, adjust=False).mean()

    # --- 신호 생성 ---
    sig = pd.Series(0, index=test_df.index, dtype=int)
    sig[ema_fast > ema_slow] = 1
    sig[ema_fast < ema_slow] = -1

    return sig.fillna(0).astype(int)
```
"""

    # -------------------------------------------------------------------------
    # 코드 정제: LLM 응답에서 마크다운 블록을 제거하고 순수 파이썬 코드만 보존
    # -------------------------------------------------------------------------
    def _clean_code(self, text: str) -> str:
        if "```python" in text:
            # 여러 블록이 있을 때 think 예시 블록이 아닌 마지막 블록을 사용
            blocks = text.split("```python")
            return blocks[-1].split("```")[0].strip()
        return text.strip()
