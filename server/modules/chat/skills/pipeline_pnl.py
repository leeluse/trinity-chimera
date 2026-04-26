"""PnL 분해 분석 파이프라인 (Long vs Short 성과 비교)"""
import logging
from typing import Any, AsyncGenerator, Dict

from server.modules.backtest.chat.chat_backtester import ChatBacktester
from server.modules.chat.skills._base import format_sse

logger = logging.getLogger(__name__)

async def run_pnl_analysis(
    message: str,
    context: Dict[str, Any],
    strategy_code: str,
    _: Dict[str, Any],
) -> AsyncGenerator[str, None]:
    try:
        if not strategy_code:
            yield format_sse({"type": "error", "content": "❌ 분석할 전략 코드가 없습니다."})
            return

        yield format_sse({"type": "stage", "stage": 1, "label": "🔍 포지션별 PnL 분해 중..."})
        
        backtester = ChatBacktester()
        bt_res = await backtester.run(strategy_code, message, context)
        
        if not bt_res.get("success"):
            yield format_sse({"type": "error", "content": f"백테스트 실패: {bt_res.get('error')}"})
            return

        metrics = bt_res.get("metrics", {})
        
        # 롱/숏 지표 추출 (BacktestEngine에서 계산되어 metrics에 포함되어 있음)
        long_ret = metrics.get("long_return", 0) * 100
        short_ret = metrics.get("short_return", 0) * 100
        long_pf = metrics.get("long_pf", 0)
        short_pf = metrics.get("short_pf", 0)
        long_count = metrics.get("long_count", 0)
        short_count = metrics.get("short_count", 0)
        total_ret = metrics.get("total_return", 0)

        # 결과 테이블 생성
        summary_md = f"""## 📊 PnL 분해 분석 (Long vs Short)

| 구분 | 전체 | Long (매수) | Short (매도) |
| :--- | :--- | :--- | :--- |
| **수익률** | **{total_ret:+.2f}%** | {long_ret:+.2f}% | {short_ret:+.2f}% |
| **Profit Factor** | {metrics.get('profit_factor', 0):.2f} | {long_pf:.2f} | {short_pf:.2f} |
| **진입 횟수** | {int(metrics.get('total_trades', 0))} | {int(long_count)} | {int(short_count)} |

### 💡 인사이트
"""
        # 단순 인사이트 로직
        if abs(long_ret) > abs(short_ret) * 2:
            insight = "- 이 전략은 주로 **Long(매수) 포지션**에서 수익이 발생하고 있습니다. 강세장 편향이 있을 수 있습니다."
        elif abs(short_ret) > abs(long_ret) * 2:
            insight = "- 이 전략은 주로 **Short(매도) 포지션**에서 수익이 발생하고 있습니다. 하락장 헤지용으로 적합할 수 있습니다."
        else:
            insight = "- Long과 Short 포지션의 수익 비중이 비교적 **균형** 잡혀 있습니다. 시장 방향성에 덜 민감한 견고한 로직입니다."

        if long_pf < 1.0 and long_count > 0:
            insight += "\n- ⚠️ Long 포지션의 PF가 1.0 미만입니다. 매수 진입 조건을 점검해 보세요."
        if short_pf < 1.0 and short_count > 0:
            insight += "\n- ⚠️ Short 포지션의 PF가 1.0 미만입니다. 매도 진입 조건을 점검해 보세요."

        yield format_sse({"type": "analysis", "content": summary_md + insight})
        
        # UI에 백테스트 카드도 함께 표시
        yield format_sse({
            "type": "backtest",
            "data": {
                "ret": f"{total_ret:+.2f}%",
                "mdd": f"{metrics.get('max_drawdown', 0):.2f}%",
                "winRate": f"{metrics.get('win_rate', 0):.1f}%",
                "sharpe": f"{metrics.get('sharpe_ratio', 0):.2f}",
                "code": strategy_code,
                "trades": int(metrics.get("total_trades", 0)),
                "pf": f"{metrics.get('profit_factor', 0):.2f}",
            },
            "payload": bt_res.get("backtest_payload"),
        })
        
        yield format_sse({"type": "done"})

    except Exception as e:
        logger.exception("PnL analysis pipeline error")
        yield format_sse({"type": "error", "content": f"분석 오류: {str(e)}"})
