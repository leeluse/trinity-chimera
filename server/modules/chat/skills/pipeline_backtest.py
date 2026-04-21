"""공통 백테스트 실행기 + 마이닝 백테스트 (WFO + Monte Carlo)"""
import asyncio
import logging
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional

import pandas as pd

from server.shared.llm.client import stream_quick_reply
from server.modules.backtest.chat.chat_backtester import ChatBacktester
from server.modules.evolution.scoring import evaluate_hard_gates, calculate_trinity_score
from server.modules.chat.prompts import TIPS_PROMPT_TEMPLATE
from server.modules.chat.skills._base import (
    format_sse,
    normalize_metrics_for_gate,
    log_strategy_to_file,
    DEFAULT_HARD_GATES,
)

logger = logging.getLogger(__name__)


async def run_backtest(
    strategy_code: str,
    strategy_title: str,
    request_message: str,
    context: Dict[str, Any],
    session_id: str,
    db,
    session_memory: Dict[str, Any],
    memory=None,
    constitution: Optional[Dict[str, Any]] = None,
    target_agent: str = "chat_global",
    chat_mutation_hint: str = "",
    is_mining_mode: bool = False,
    persona=None,
    seed=None,
    prev_metrics: Optional[Dict[str, Any]] = None,
) -> AsyncGenerator[str, None]:
    try:
        if is_mining_mode:
            async for ev in _run_mining_backtest(
                strategy_code, strategy_title, request_message,
                context, session_id, db, session_memory, persona, seed,
            ):
                yield ev
            return

        engine = ChatBacktester()
        bt_res = await engine.run(strategy_code, request_message, context)

        if not bt_res.get("success"):
            yield format_sse({"type": "error", "content": f"백테스트 실패: {bt_res.get('error')}"})
            logger.error(f"[backtest] {bt_res.get('error')}")
            return

        metrics = bt_res.get("metrics", {})

        if int(metrics.get("total_trades", 0)) == 0:
            yield format_sse({"type": "analysis", "content": (
                "\n🚫 **진입 신호 0건** — 백테스트 기간 동안 거래가 한 건도 발생하지 않았습니다.\n"
                "진입 조건이 너무 엄격합니다. 전략을 수정하거나 새로 생성해 주세요.\n"
            )})
            return

        gate_metrics = normalize_metrics_for_gate(metrics)

        gates = (constitution.get("hard_gates", DEFAULT_HARD_GATES) if constitution else DEFAULT_HARD_GATES)
        hard_ok, hard_reasons = evaluate_hard_gates(gate_metrics, gates)

        if memory:
            fingerprint = memory.compute_fingerprint(strategy_code)
            status = "accepted_chat_gate" if hard_ok else "rejected_chat_gate"
            reason = "hard_gate_passed" if hard_ok else "; ".join(hard_reasons)
            memory.log_experiment(
                agent_id=target_agent, status=status, stage="chat_backtest",
                reason=reason, fingerprint=fingerprint,
                metrics=gate_metrics, mutation_hint=chat_mutation_hint,
            )
            if hard_ok:
                memory.log_accepted(agent_id=target_agent, strategy_id=None,
                                    fingerprint=fingerprint, metrics=gate_metrics)
            else:
                memory.log_failure_pattern(
                    agent_id=target_agent,
                    reason=f"chat_hard_gate_failed: {reason}",
                    fingerprint=fingerprint, metrics=gate_metrics,
                )

        backtest_data = {
            "ret": f"{metrics.get('total_return', 0):+.2f}%",
            "mdd": f"{metrics.get('max_drawdown', 0):.2f}%",
            "winRate": f"{metrics.get('win_rate', 0):.1f}%",
            "sharpe": f"{metrics.get('sharpe_ratio', 0):.2f}",
        }
        yield format_sse({"type": "backtest", "data": {
            **backtest_data,
            "code": strategy_code,
            "trades": metrics.get("total_trades", 0),
            "pf": f"{metrics.get('profit_factor', 0):.2f}",
        }, "payload": bt_res.get("backtest_payload")})
        
        yield format_sse({"type": "stage", "stage": 5, "label": "🏆 전략 생성 및 백테스트 완료!"})
        
        bt_summary = f"{strategy_title} | 수익률 {backtest_data['ret']} MDD {backtest_data['mdd']} Sharpe {backtest_data['sharpe']}"
        await db.save_chat_message(session_id, "assistant", bt_summary, "backtest", {
            **backtest_data,
            "title": strategy_title,
            "code": strategy_code,
            "metrics": metrics,
            "trades": metrics.get("total_trades", 0),
            "pf": f"{metrics.get('profit_factor', 0):.2f}",
        })

        session_memory[session_id] = {
            "code": strategy_code,
            "title": strategy_title,
            "metrics": metrics,
            "gate_metrics": gate_metrics,
            "timestamp": datetime.now().isoformat(),
        }

        if prev_metrics:
            new_ret = metrics.get("total_return", 0)
            old_ret = prev_metrics.get("total_return", 0)
            new_mdd = metrics.get("max_drawdown", 0)
            old_mdd = prev_metrics.get("max_drawdown", 0)
            new_sharpe = metrics.get("sharpe_ratio", 0)
            old_sharpe = prev_metrics.get("sharpe_ratio", 0)
            delta_ret = new_ret - old_ret
            delta_mdd = new_mdd - old_mdd

            ret_icon = "✅" if delta_ret > 0 else ("⚠️" if delta_ret < 0 else "➡️")
            comparison = (
                "\n**[수정 전후 비교]**\n"
                f"| 지표 | 기존 | 수정 후 | 변화 |\n|---|---|---|---|\n"
                f"| 수익률 | {old_ret:+.2f}% | {new_ret:+.2f}% | {ret_icon} {delta_ret:+.2f}% |\n"
                f"| MDD | {old_mdd:.2f}% | {new_mdd:.2f}% | {'✅' if new_mdd < old_mdd else '⚠️'} {delta_mdd:+.2f}% |\n"
                f"| Sharpe | {old_sharpe:.2f} | {new_sharpe:.2f} | {'✅' if new_sharpe > old_sharpe else '⚠️'} |\n"
                f"| 거래 수 | {int(prev_metrics.get('total_trades',0))} | {int(metrics.get('total_trades',0))} | |\n"
            )
            yield format_sse({"type": "analysis", "content": comparison})

        if not hard_ok:
            yield format_sse({"type": "analysis", "content": (
                "\n⚠️ **하드게이트 미통과** — 자동 채택/배포 비권장\n"
                + "\n".join(f"- {r}" for r in hard_reasons) + "\n"
            )})

        tips_full = ""
        async for chunk in stream_quick_reply(TIPS_PROMPT_TEMPLATE.format(metrics=metrics)):
            tips_full += chunk
            yield format_sse({"type": "analysis", "content": chunk})
        await db.save_chat_message(session_id, "assistant", tips_full, "text")

        log_strategy_to_file(request_message, metrics)

    except Exception as e:
        logger.exception("백테스트 실행 오류")
        yield format_sse({"type": "error", "content": str(e)})


async def _run_mining_backtest(
    strategy_code: str,
    strategy_title: str,
    request_message: str,
    context: Dict[str, Any],
    session_id: str,
    db,
    session_memory: Dict[str, Any],
    persona=None,
    seed=None,
) -> AsyncGenerator[str, None]:
    """WFO + Monte Carlo 전체 검증"""
    try:
        from server.modules.backtest.backtest_engine import BacktestEngine, strategy_from_code
        from server.shared.market.provider import fetch_ohlcv_dataframe

        symbol = context.get("symbol", "BTCUSDT")
        timeframe = context.get("timeframe", "1h")
        end_ms = int(datetime.now().timestamp() * 1000)
        start_ms = end_ms - (365 * 24 * 60 * 60 * 1000)

        yield format_sse({"type": "stage", "stage": 4, "label": "📊 마켓 데이터 수집 중..."})
        df = fetch_ohlcv_dataframe(symbol=symbol, interval=timeframe,
                                   limit=10000, start_ms=start_ms, end_ms=end_ms)
        if df is None or df.empty:
            yield format_sse({"type": "error", "content": "마켓 데이터 수집 실패 — 마이닝 중단"})
            return
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df.set_index("timestamp", inplace=True)

        engine = BacktestEngine(df, freq=24 if timeframe == "1h" else 1)
        strategy_fn = strategy_from_code(strategy_code)

        yield format_sse({"type": "analysis", "content": f"\n⚙️ **{persona['name'] if persona else ''}** 고강도 검증 시작...\n"})

        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def progress_callback(msg: str):
            loop.call_soon_threadsafe(queue.put_nowait, msg)

        validation_task = asyncio.create_task(asyncio.to_thread(
            engine.run_full_validation,
            strategy_fn=strategy_fn,
            strategy_name=strategy_title,
            run_test_set=False,
            callback=progress_callback,
        ))

        try:
            while not validation_task.done() or not queue.empty():
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=0.1)
                    yield format_sse({"type": "analysis", "content": f"  {msg}\n"})
                except asyncio.TimeoutError:
                    if validation_task.done():
                        break
            validation_res = await asyncio.wait_for(asyncio.shield(validation_task), timeout=360)
        except asyncio.TimeoutError:
            validation_task.cancel()
            yield format_sse({"type": "error", "content": "⏱️ 검증 타임아웃 (6분 초과) — 마이닝 중단"})
            return

        yield format_sse({"type": "stage", "stage": 5, "label": "🏆 전략 품질 판정 중..."})
        wfo = validation_res.wfo_results
        n = max(len(wfo), 1)

        # ── 거래 0건 감지 ─────────────────────────────────────────
        total_trades_all = sum(getattr(r, "total_trades", 0) for r in wfo)
        if total_trades_all == 0:
            yield format_sse({"type": "analysis", "content": (
                "\n🚫 **진입 신호 0건** — 모든 WFO 구간에서 거래가 발생하지 않았습니다.\n\n"
                "원인: 진입 조건(지표 임계값, 필터)이 너무 엄격하거나 서로 충돌합니다.\n"
                "→ 다시 채굴하면 더 완화된 조건의 전략을 생성합니다.\n"
            )})
            return

        avg_return = sum(r.total_return for r in wfo) / n if wfo else 0.0
        avg_sharpe = sum(r.sharpe for r in wfo) / n if wfo else 0.0
        worst_mdd = -abs(max((abs(r.max_drawdown) for r in wfo), default=0.0))
        trinity_score = calculate_trinity_score(avg_return, avg_sharpe, worst_mdd)
        score_color = "🟢 GOOD" if trinity_score >= 70 else ("🟡 FAIR" if trinity_score >= 40 else "🔴 RISKY")

        yield format_sse({"type": "analysis", "content": (
            f"\n### 🛡️ 트리니티 점수: **{trinity_score:.1f}/100** ({score_color})\n"
            f"```text\n{validation_res.summary()}\n```"
        )})

        if validation_res.is_robust:
            try:
                mining_key = f"mining_{datetime.now().strftime('%y%m%d_%H%M%S')}"
                db.save_system_strategy(
                    strategy_key=mining_key,
                    code=strategy_code,
                    params={
                        "strategy_key": mining_key,
                        "display_name": f"💎 [{persona['name'] if persona else ''}] {seed or ''}",
                        "description": f"채굴 전략 | Trinity Score: {trinity_score:.1f}",
                    },
                    rationale=f"Trinity Score: {trinity_score:.1f}",
                )
                yield format_sse({"type": "analysis", "content": f"\n✅ 금고(`{mining_key}`)에 보관되었습니다."})
            except Exception as e:
                logger.error(f"마이닝 전략 저장 실패: {e}")
        else:
            yield format_sse({"type": "analysis", "content": "\n⚠️ 견고함 기준 미달 — 금고 미보관."})

    except Exception as e:
        logger.error(f"마이닝 백테스트 오류: {e}")
        # 경량 백테스트로 폴백
        chat_engine = ChatBacktester()
        bt_res = await chat_engine.run(strategy_code, request_message, context)
        if bt_res.get("success"):
            metrics = bt_res.get("metrics", {})
            yield format_sse({"type": "backtest", "data": {
                "ret": f"{metrics.get('total_return', 0):+.2f}%",
                "mdd": f"{metrics.get('max_drawdown', 0):.2f}%",
                "winRate": f"{metrics.get('win_rate', 0):.1f}%",
                "sharpe": f"{metrics.get('sharpe_ratio', 0):.2f}",
            }, "payload": bt_res.get("backtest_payload")})
            session_memory[session_id] = {
                "code": strategy_code, "title": strategy_title,
                "metrics": metrics, "timestamp": datetime.now().isoformat(),
            }
