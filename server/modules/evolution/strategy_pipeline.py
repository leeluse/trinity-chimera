"""
LLM 전략 생성기 → 백테스트 엔진 연결
--------------------------------------
LLM이 독특한 전략 코드를 생성하고,
backtest_engine.py가 신뢰도 높게 검증하는 파이프라인.

Usage:
    pipeline = StrategyPipeline(df)
    winners = pipeline.run(n_strategies=8, generations=3)
"""

import json
import random
import textwrap
import traceback
from typing import Optional
from datetime import datetime, timedelta
import argparse
import asyncio

from server.shared.llm.llm_client import build_default_llm_service, LLMUnavailableError
from server.modules.evolution.constants import BANNED_INDICATORS, CROSS_DOMAIN_SEEDS, PERSONAS
from dotenv import load_dotenv

load_dotenv() # .env 파일의 API 키 등을 로드합니다.
import numpy as np
import pandas as pd

from server.modules.backtest.backtest_engine import BacktestEngine, strategy_from_code, ValidationResult
from server.shared.market.provider import fetch_ohlcv_dataframe




# ─────────────────────────────────────────────
# LLM 전략 생성기
# ─────────────────────────────────────────────

class LLMStrategyGenerator:

    DESIGN_CONTRACT = textwrap.dedent("""
    ## 전략 설계 규격 (코드 생성 전)

    JSON 형식으로 다음을 작성해라:
    {
        "name": "전략 이름 (자연현상/동물 이름)",
        "hypothesis": "이 전략이 작동하는 시장 비효율성 (한 문장)",
        "hidden_assumption": "이 전략의 숨겨진 가정 (한 문장)",
        "entry_logic": "진입 조건 설명 (한 문장, 구체적 지표명과 수치 포함)",
        "exit_logic": "청산 조건 설명 (한 문장, stop loss, take profit 같은 메커니즘)",
        "expected_trades": "기대 거래 수 (예: 100-200, 매 시간 5-10건 등)",
        "risk_management": "리스크 관리 방식 (포지션 크기, 손실 한계 등)",
        "expected_regime": "bull/bear/sideways/all 중 하나"
    }

    검증 포인트:
    - 진입 조건과 청산 조건이 명확히 구분되는가?
    - 거래 수가 현실적인가? (너무 적으면 10건 이상, 너무 많으면 과거 데이터 비향)
    - 사용할 지표가 pandas/numpy로 구현 가능한가?
    """)

    SIGNAL_CONTRACT = textwrap.dedent("""
    ## 반드시 지켜야 할 코드 계약

    다음 함수를 **정확히 이 시그니처로** 구현해라:

    ```python
    def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:
        \"\"\"
        train_df: 파라미터 최적화/패턴 학습용 (보지 않아도 됨)
        test_df : 실제 신호 생성 대상
        반환: test_df.index와 같은 인덱스를 가진 pd.Series
              값은 반드시 1 (롱), -1 (숏), 0 (플랫) 중 하나
        \"\"\"
    ```

    - OHLCV 컬럼명: open, high, low, close, volume (모두 소문자)
    - 미래 데이터 참조 금지: shift(-N) 사용 금지
    - **과거 데이터 참조**: 반드시 `df['close'].shift(1)` 같이 pandas 표준 방식을 사용해라. `prev_close` 같은 정의되지 않은 변수는 절대 사용 금지.
    - 외부 라이브러리: numpy, pandas만 사용 가능
    - 수수료/슬리피지는 엔진이 처리하니 코드에 포함하지 마라
    - **거래 빈도**: 너무 엄격한 조건으로 거래가 0건이 되지 않도록 유의해라.
    - 반드시 실행 가능한 완전한 코드
    """)

    def __init__(self, model: str = "claude-3-5-sonnet"):
        self.llm_service = build_default_llm_service()
        self.model = model

    async def generate_design(
        self,
        persona: Optional[dict] = None,
        seed: Optional[str] = None,
        parent: Optional[dict] = None,
        generation: int = 1,
        feedback: Optional[str] = None,
    ) -> dict:
        """전략 설계만 생성 (코드 생성 전 단계)."""
        persona = persona or random.choice(PERSONAS)
        seed = seed or random.choice(CROSS_DOMAIN_SEEDS)

        feedback_instruction = ""
        if feedback:
            feedback_instruction = f"""
            ## 이전 설계 피드백 (반드시 반영할 것)
            {feedback}
            위 문제를 해결하여 설계를 다시 작성해라.
            """

        if parent:
            task = f"""
            ## 변이 지시
            부모 설계:
            - 가설: {parent.get('hypothesis', '?')}
            - 진입: {parent.get('entry_logic', '?')}
            - 청산: {parent.get('exit_logic', '?')}
            - 기대 거래: {parent.get('expected_trades', '?')}
            부모 성과: Sharpe={parent.get('sharpe', '?'):.2f}

            이 설계를 **한 가지만** 변이시켜라 (진입 조건 OR 청산 방식 OR 리스크 관리).
            """
        else:
            task = f"""
            ## 전략 설계 지시
            페르소나: {persona['name']}
            세계관: {persona['worldview']}
            스타일: {persona['style']}
            크로스 도메인 씨드: {seed}
            """

        prompt = f"""
        너는 독창적인 퀀트 전략 설계자다. (세대: {generation})

        {feedback_instruction}

        {task}

        ## 금지 지표
        다음은 절대 사용하지 마라: {', '.join(BANNED_INDICATORS)}

        {self.DESIGN_CONTRACT}

        JSON만 출력해라. 다른 텍스트 없이.
        """

        if not self.llm_service:
            raise RuntimeError("LLM 서비스가 설정되지 않았습니다. .env 파일을 확인하세요.")

        raw_response = await self.llm_service.generate(prompt)
        raw = raw_response.strip()

        try:
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0]
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0]
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {
                "name": f"Design-{generation}-{random.randint(100,999)}",
                "hypothesis": "파싱 실패",
                "hidden_assumption": "",
                "entry_logic": raw[:100],
                "exit_logic": "unknown",
                "expected_trades": "unknown",
                "risk_management": "unknown",
                "expected_regime": "all",
            }

        data["persona"] = persona["name"]
        data["seed"] = seed
        data["generation"] = generation
        return data

    def validate_design(self, design: dict) -> tuple[bool, list[str]]:
        """설계의 논리성을 검증. 반환: (is_valid, warnings)"""
        warnings = []

        if not design.get("entry_logic") or len(design["entry_logic"]) < 10:
            warnings.append("❌ 진입 조건이 명확하지 않음")

        if not design.get("exit_logic") or len(design["exit_logic"]) < 10:
            warnings.append("❌ 청산 조건이 명확하지 않음")

        # 거래 빈도 체크 (너무 적거나 너무 많으면 경고)
        trades_str = str(design.get("expected_trades", "")).lower()
        if "0" in trades_str or "none" in trades_str or "no trade" in trades_str:
            warnings.append("⚠️  거래가 0건으로 예상됨 (진입 조건 너무 엄격?)")

        if not design.get("hypothesis"):
            warnings.append("⚠️  작동 가설이 없음")

        if not design.get("risk_management"):
            warnings.append("⚠️  리스크 관리 방식 미명시")

        is_valid = len([w for w in warnings if "❌" in w]) == 0
        return is_valid, warnings

    async def generate_code_from_design(
        self,
        design: dict,
        generation: int = 1,
        feedback: Optional[str] = None,
    ) -> dict:
        """설계에 기반해 코드 생성."""
        feedback_instruction = ""
        if feedback:
            feedback_instruction = f"""
            ## 이전 코드 피드백 (반드시 반영할 것)
            {feedback}
            위 문제를 해결하여 코드를 다시 작성해라.
            """

        prompt = f"""
        너는 정확한 파이썬 코더다.

        {feedback_instruction}

        다음 설계를 **정확히** 따라 코드를 구현해라:

        전략명: {design['name']}
        가설: {design['hypothesis']}
        진입 조건: {design['entry_logic']}
        청산 조건: {design['exit_logic']}
        기대 거래: {design['expected_trades']}
        리스크 관리: {design['risk_management']}

        {self.SIGNAL_CONTRACT}

        출력 템플릿 (지표 예시):
        ```python
        import numpy as np
        import pandas as pd

        def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:
            close = test_df['close']
            high  = test_df['high']
            low   = test_df['low']
            vol   = test_df['volume']

            # 설계를 따라 지표 계산
            # ...

            sig = pd.Series(0, index=test_df.index, dtype=int)
            # 설계의 진입/청산 로직을 구현
            # ...

            return sig.fillna(0).astype(int)
        ```

        Python 코드만 출력해라.
        """

        if not self.llm_service:
            raise RuntimeError("LLM 서비스가 설정되지 않았습니다. .env 파일을 확인하세요.")

        raw_response = await self.llm_service.generate(prompt)
        code = self._extract_code(raw_response)

        design["code"] = code
        design["generation"] = generation
        return design

    def _extract_code(self, text: str) -> str:
        """LLM 응답에서 Python 코드만 추출."""
        if "```python" in text:
            blocks = text.split("```python")
            return blocks[-1].split("```")[0].strip()
        elif "```" in text:
            blocks = text.split("```")
            if len(blocks) >= 3:
                return blocks[1].strip()
        return text.strip()

    async def generate(
        self,
        persona: Optional[dict] = None,
        seed: Optional[str] = None,
        parent: Optional[dict] = None,
        generation: int = 1,
        feedback: Optional[str] = None,
    ) -> dict:
        """레거시 호환성: 설계→코드 2단계 통합."""
        design = await self.generate_design(persona, seed, parent, generation, feedback)
        return await self.generate_code_from_design(design, generation)


# ─────────────────────────────────────────────
# 전체 파이프라인
# ─────────────────────────────────────────────

class StrategyPipeline:
    """
    LLM 전략 생성 → 백테스트 검증 → 진화 루프
    """

    def __init__(
        self,
        df: pd.DataFrame,
        fee_rate: float = 0.001,
        slippage: float = 0.0005,
        freq: int = 24,
        llm_model: str = "claude-sonnet-4-6",
    ):
        self.engine = BacktestEngine(df, fee_rate, slippage, freq=freq)
        self.generator = LLMStrategyGenerator(model=llm_model)
        self.history: list[dict] = []

    @staticmethod
    def _is_transient_llm_error(exc: Exception) -> bool:
        text = str(exc).lower()
        if isinstance(exc, LLMUnavailableError):
            return True
        return any(
            key in text
            for key in (
                "connecttimeout",
                "timed out",
                "operation timed out",
                "connection refused",
                "all connection attempts failed",
                "llm unavailable",
                "llm call failed",
            )
        )

    async def run(
        self,
        n_strategies: int = 6,
        generations: int = 3,
        top_k: int = 2,           # 세대당 생존자 수
        run_test_set: bool = False,
    ) -> list[dict]:
        """
        전체 진화 루프 실행.
        Returns: 최종 생존 전략 목록 (성과 포함)
        """
        pool = []

        print(f"\n{'='*55}")
        print(f"  전략 진화 파이프라인 시작")
        print(f"  {n_strategies}개 초기 생성 → {generations}세대 진화 → 상위 {top_k}개 선발")
        print(f"{'='*55}\n")

        # ── 1세대: 완전 랜덤 생성 ──────────────────
        print(f"[ 1세대 ] {n_strategies}개 전략 생성 중...")
        for i in range(n_strategies):
            candidate = await self._generate_and_validate(generation=1, idx=i)
            if candidate:
                pool.append(candidate)

        if not pool:
            print("1세대 전략 생성 실패")
            return []

        # ── N세대 진화 ────────────────────────────
        for gen in range(2, generations + 1):
            # 생존자 선택 (Sharpe 기준)
            pool.sort(key=lambda x: x.get("sharpe", -999), reverse=True)
            survivors = pool[:top_k]
            print(f"\n[ {gen}세대 생존자 ] {[s['name'] for s in survivors]}")

            new_pool = survivors.copy()
            target = max(n_strategies, len(survivors) * 2)

            while len(new_pool) < target:
                parent = survivors[len(new_pool) % len(survivors)]
                # 약점 추출
                parent["weakness"] = self._identify_weakness(parent)
                candidate = await self._generate_and_validate(
                    generation=gen,
                    idx=len(new_pool),
                    parent=parent,
                )
                if candidate:
                    new_pool.append(candidate)

            pool = new_pool

        # ── 최종 정렬 및 테스트셋 실행 ────────────
        pool.sort(key=lambda x: x.get("sharpe", -999), reverse=True)
        winners = pool[:top_k]

        if run_test_set:
            print(f"\n[ 최종 테스트셋 평가 ] {[w['name'] for w in winners]}")
            for w in winners:
                try:
                    fn = strategy_from_code(w["code"])
                    result = self.engine.run_full_validation(
                        fn, w["name"], run_test_set=True
                    )
                    w["final_result"] = result
                    w["test_verdict"] = result.verdict
                except Exception as e:
                    w["test_verdict"] = f"실패: {e}"

        self._print_final_report(winners)
        return winners

    async def _generate_and_validate(
        self,
        generation: int,
        idx: int,
        parent: Optional[dict] = None,
        max_retries: int = 3,
    ) -> Optional[dict]:
        prefix = f"  [{generation}세대-{idx+1:02d}]"
        last_design_feedback = None
        last_code_feedback = None

        for attempt in range(max_retries):
            try:
                # ─── 1단계: 전략 설계 생성 ───
                design = await self.generator.generate_design(
                    parent=parent,
                    generation=generation,
                    feedback=last_design_feedback
                )

                if attempt > 0:
                    print(f"{prefix} 설계 재생성({attempt}/{max_retries}): {design['name']}")
                else:
                    print(f"{prefix} 설계: {design['name']}")

                # ─── 2단계: 설계 검증 ───
                is_valid, warnings = self.generator.validate_design(design)
                if warnings:
                    for w in warnings:
                        print(f"{prefix}  {w}")

                if not is_valid:
                    # 심각한 오류가 있으면 설계 단계에서 재생성
                    critical_warnings = [w for w in warnings if "❌" in w]
                    last_design_feedback = f"설계에 문제가 있습니다: {' / '.join(critical_warnings)}\n다시 설계를 작성해주세요."
                    print(f"{prefix}  설계 재조정 중...")
                    continue

                print(f"{prefix}  ✓ 진입: {design['entry_logic'][:50]}...")
                print(f"{prefix}  ✓ 청산: {design['exit_logic'][:50]}...")
                print(f"{prefix}  ✓ 거래 예상: {design['expected_trades']}")

                # ─── 3단계: 설계 기반 코드 생성 ───
                strategy = await self.generator.generate_code_from_design(
                    design,
                    generation=generation,
                    feedback=last_code_feedback
                )
                print(f"{prefix}  코드 생성 완료")

                # ─── 4단계: 코드 실행 가능 여부 확인 ───
                try:
                    fn = strategy_from_code(strategy["code"])
                except Exception as code_err:
                    last_code_feedback = f"코드 실행 중 에러: {str(code_err)[:100]}\n설계를 유지하면서 코드만 수정하세요."
                    print(f"{prefix}  ❌ 코드 에러 - 재생성 중...")
                    continue

                # ─── 5단계: 백테스트 실행 ───
                result = self.engine.run_full_validation(
                    fn,
                    strategy_name=strategy["name"],
                    run_test_set=False,
                )

                # ─── 6단계: 검증 결과 분석 ───
                if not result.wfo_results:
                    last_code_feedback = "거래가 발생하지 않았습니다(구간 에러). 진입 조건을 완화하세요."
                    print(f"{prefix}  ⚠️  거래 없음 - 코드 수정 중...")
                    continue

                total_trades = sum(r.n_trades for r in result.wfo_results)
                if total_trades < 10:
                    last_code_feedback = f"거래가 {total_trades}건으로 너무 적습니다(최소 10건). 진입 조건을 더 완화하세요."
                    print(f"{prefix}  ⚠️  거래 부족({total_trades}건) - 코드 수정 중...")
                    continue

                # 성공
                sharpes = [r.sharpe for r in result.wfo_results]
                strategy["sharpe"] = float(np.mean(sharpes))
                strategy["sharpe_std"] = float(np.std(sharpes))
                strategy["max_dd"] = float(min(r.max_drawdown for r in result.wfo_results))
                strategy["is_robust"] = result.is_robust
                strategy["verdict"] = result.verdict

                status = "✅" if result.is_robust else "⚠️ "
                print(f"{prefix} {status} Sharpe={strategy['sharpe']:.2f} "
                      f"MDD={strategy.get('max_dd', 0):.1%} (거래 {total_trades}건)")

                self.history.append(strategy)
                return strategy

            except Exception as e:
                err_msg = str(e)
                last_code_feedback = f"예상 밖의 에러: {err_msg[:100]}"
                transient = self._is_transient_llm_error(e)
                if transient:
                    print(f"{prefix} ⏳ LLM 연결 오류: {err_msg[:80]}... (잠시 후 재시도)")
                    await asyncio.sleep(min(2 * (attempt + 1), 8))
                else:
                    print(f"{prefix} ❌ 에러: {err_msg[:50]}...")
                if attempt == max_retries - 1 and not transient:
                    traceback.print_exc()

        return None

    def _identify_weakness(self, strategy: dict) -> str:
        """WFO 결과에서 약점 패턴 추출"""
        verdict = strategy.get("verdict", "")
        max_dd = strategy.get("max_dd", 0)
        sharpe_std = strategy.get("sharpe_std", 0)

        if max_dd < -0.25:
            return f"최대 낙폭 {max_dd:.1%} — 하방 리스크 과다"
        if sharpe_std > 1.0:
            return f"Sharpe 표준편차 {sharpe_std:.2f} — 구간별 성과 불안정"
        if "MDD" in verdict:
            return "낙폭 과다"
        if "Sharpe" in verdict:
            return "일관성 부족"
        return "불명확"

    def _print_final_report(self, winners: list[dict]):
        print(f"\n{'='*55}")
        print(f"  최종 생존 전략")
        print(f"{'='*55}")
        for i, w in enumerate(winners):
            print(f"\n  #{i+1} {w['name']} (세대 {w.get('generation', '?')})")
            print(f"  페르소나: {w.get('persona', '-')}")
            print(f"  가설:     {w.get('hypothesis', '-')}")
            print(f"  숨겨진 가정: {w.get('hidden_assumption', '-')}")
            print(f"  Sharpe (WFO 평균): {w.get('sharpe', 0):.2f}")
            print(f"  최악 MDD:         {w.get('max_dd', 0):.1%}")
            print(f"  판정: {w.get('verdict', '-')}")
        print(f"{'='*55}")


async def main():
    parser = argparse.ArgumentParser(description='Trinity Strategy Evolution Pipeline')
    parser.add_argument('--symbol', type=str, default='BTCUSDT', help='거래 심볼 (기본: BTCUSDT)')
    parser.add_argument('--timeframe', type=str, default='1h', help='타임프레임 (기본: 1h)')
    parser.add_argument('--n', type=int, default=4, help='세대당 생성할 전략 수 (기본: 4)')
    parser.add_argument('--gen', type=int, default=2, help='진화 세대 수 (기본: 2)')
    parser.add_argument('--days', type=int, default=180, help='데이터 수집 기간 (일단위, 기본: 180)')
    
    args = parser.parse_args()

    print(f"\n[Mining] '{args.symbol}' 데이터 수집 중 ({args.days}일)...")
    end_ms = int(datetime.now().timestamp() * 1000)
    start_ms = end_ms - (args.days * 24 * 60 * 60 * 1000)
    
    try:
        df = fetch_ohlcv_dataframe(args.symbol, args.timeframe, start_ms, end_ms)
        if df.empty:
            print("❌ 데이터를 가져오지 못했습니다. 심볼이나 기간을 확인하세요.")
            return

        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        
        pipeline = StrategyPipeline(df, freq=24 if args.timeframe == '1h' else 1)
        await pipeline.run(n_strategies=args.n, generations=args.gen, run_test_set=True)
        
    except Exception as e:
        print(f"❌ 실행 중 오류 발생: {e}")
        text = str(e).lower()
        if not any(
            key in text for key in (
                "connecttimeout",
                "timed out",
                "operation timed out",
                "llm",
            )
        ):
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
