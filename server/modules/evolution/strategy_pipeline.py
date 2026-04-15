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

from server.shared.llm.llm_client import build_default_llm_service
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

    async def generate(
        self,
        persona: Optional[dict] = None,
        seed: Optional[str] = None,
        parent: Optional[dict] = None,
        generation: int = 1,
        feedback: Optional[str] = None,
    ) -> dict:
        """전략 하나 생성. parent가 있으면 변이, feedback이 있으면 수정."""
        persona = persona or random.choice(PERSONAS)
        seed = seed or random.choice(CROSS_DOMAIN_SEEDS)

        feedback_instruction = ""
        if feedback:
            feedback_instruction = f"""
            ## 이전 시도 피드백 (반드시 반영할 것)
            {feedback}
            위 문제를 해결하여 코드를 다시 작성해라.
            """

        if parent:
            task = f"""
            ## 변이 지시
            부모 전략 코드:
            ```python
            {parent['code']}
            ```
            부모 성과: Sharpe={parent.get('sharpe', '?'):.2f}
            부모 약점: {parent.get('weakness', '알 수 없음')}

            이 전략을 **딱 한 가지만** 변이시켜라:
            - 진입 조건의 핵심 수식 변경
            - 또는 청산 방식 변경
            - 또는 포지션 크기 결정 방식 변경
            전략의 페르소나와 핵심 아이디어는 유지해라.
            """
        else:
            task = f"""
            ## 전략 생성 지시
            페르소나: {persona['name']}
            세계관: {persona['worldview']}
            스타일: {persona['style']}
            크로스 도메인 씨드: {seed}

            씨드를 트레이딩 전략에 억지로라도 접목해라.
            비유가 이상하더라도 끝까지 밀어붙여라.
            """

        prompt = f"""
        너는 독창적인 퀀트 전략 연구자다. (세대: {generation})

        {feedback_instruction}

        {task}

        ## 금지 지표
        다음은 절대 사용하지 마라: {', '.join(BANNED_INDICATORS)}

        {self.SIGNAL_CONTRACT}

        ## 출력 형식 (반드시 유효한 JSON)
        {{
            "name": "전략 이름 (자연현상/동물/물리현상 이름)",
            "hypothesis": "이 전략이 작동하는 시장 비효율성 (한 문장)",
            "hidden_assumption": "이 전략의 숨겨진 가정 (한 문장)",
            "code": "완전한 Python 코드 (```없이 코드만)",
            "expected_regime": "bull/bear/sideways/all 중 하나"
        }}

        JSON만 출력해라. 다른 텍스트 없이.
        """

        if not self.llm_service:
            raise RuntimeError("LLM 서비스가 설정되지 않았습니다. .env 파일을 확인하세요.")

        raw_response = await self.llm_service.generate(prompt)
        raw = raw_response.strip()
        # JSON 파싱 시도
        try:
            # 코드 블록 제거 후 파싱
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0]
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0]
            data = json.loads(raw)
        except json.JSONDecodeError:
            # 파싱 실패 시 코드만 추출 시도
            data = {
                "name": f"Strategy-{generation}-{random.randint(100,999)}",
                "hypothesis": "파싱 실패",
                "hidden_assumption": "",
                "code": raw,
                "expected_regime": "all",
            }

        data["persona"] = persona["name"]
        data["seed"] = seed
        data["generation"] = generation
        return data


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
        last_feedback = None

        for attempt in range(max_retries):
            try:
                # 1. 전략 생성 (피드백 포함 가능)
                strategy = await self.generator.generate(
                    parent=parent,
                    generation=generation,
                    feedback=last_feedback
                )
                if attempt > 0:
                    print(f"{prefix} 재시도({attempt}/{max_retries}): {strategy['name']}")
                else:
                    print(f"{prefix} 생성: {strategy['name']}")

                # 2. 코드 실행 가능 여부 확인
                fn = strategy_from_code(strategy["code"])

                # 3. 백테스트 실행
                result = self.engine.run_full_validation(
                    fn,
                    strategy_name=strategy["name"],
                    run_test_set=False,
                )

                # 4. 검증 결과 분석 (에러나 거래 없음 확인)
                if not result.wfo_results:
                    # WFO 결과가 없으면 (주로 거래가 너무 적거나 에러)
                    last_feedback = "백테스트 구간 성과를 산출할 수 없습니다. 거래가 너무 적거나(최소 20건 이상 필요), 진입 조건이 너무 엄격할 수 있습니다."
                    print(f"{prefix} ⚠️  거래 부족 또는 구간 에러 - 다시 짜는 중...")
                    continue

                total_trades = sum(r.n_trades for r in result.wfo_results)
                if total_trades < 10:
                    last_feedback = f"전체 WFO 구간 동안 거래가 {total_trades}건으로 너무 적습니다. 진입 조건을 더 완화하여 유의미한 거래 횟수를 확보하세요."
                    print(f"{prefix} ⚠️  거래 횟수 부족 ({total_trades}건) - 다시 짜는 중...")
                    continue

                # 성공적으로 검증된 경우 지표 추출
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
                # 런타임 에러 발생 시 피드백으로 전달
                err_msg = str(e)
                last_feedback = f"코드 실행 중 다음 에러가 발생했습니다: {err_msg}\n변수 정의나 pandas 문법을 확인하고 에러를 수정하세요."
                print(f"{prefix} ❌ 에러 발생: {err_msg[:50]}... - 다시 짜는 중...")
                if attempt == max_retries - 1:
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
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
