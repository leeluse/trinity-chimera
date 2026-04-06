"""
LLM 기반 자가 개선 서비스

핵심 기능:
- 백테스팅 실행
- LLM 피드백 생성
- 전략 개선 사이클 관리
"""

import asyncio
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

from ..models.agent import (
    AgentImprovementRequest, BacktestResult, LLMFeedback,
    ImprovementProgress, ImprovementStatus, AgentPerformanceMetrics
)

logger = logging.getLogger(__name__)


class SelfImprovementService:
    """LLM 자가 개선 서비스"""

    def __init__(self):
        self.improvements: Dict[str, Dict] = {}  # 개선 요청 저장소
        self.backtest_results: Dict[str, BacktestResult] = {}
        self.feedback_history: Dict[str, List[LLMFeedback]] = {}
        self.agent_performance: Dict[str, AgentPerformanceMetrics] = {}

    async def request_improvement(
        self,
        agent_id: str,
        current_strategy: Dict[str, Any]
    ) -> Dict[str, Any]:
        """LLM 자가 개선 요청 시작"""

        improvement_id = str(uuid.uuid4())

        # 개선 요청 저장
        self.improvements[improvement_id] = {
            "agent_id": agent_id,
            "current_strategy": current_strategy,
            "status": ImprovementStatus.REQUESTED,
            "created_at": datetime.now(),
            "progress": 0.0
        }

        # 비동기로 개선 프로세스 시작
        asyncio.create_task(self._run_improvement_process(improvement_id))

        return {
            "improvement_id": improvement_id,
            "status": "started",
            "message": "LLM 개선 프로세스가 시작되었습니다"
        }

    async def _run_improvement_process(self, improvement_id: str):
        """개선 프로세스 실행"""

        improvement = self.improvements[improvement_id]
        agent_id = improvement["agent_id"]

        try:
            # 1. 백테스팅 실행
            improvement["status"] = ImprovementStatus.BACKTESTING
            improvement["progress"] = 25.0

            backtest_result = await self._run_backtest(
                agent_id,
                improvement["current_strategy"]
            )
            self.backtest_results[improvement_id] = backtest_result

            # 2. LLM 분석
            improvement["status"] = ImprovementStatus.ANALYZING
            improvement["progress"] = 50.0

            llm_feedback = await self._analyze_with_llm(agent_id, backtest_result)

            # 피드백 저장
            if agent_id not in self.feedback_history:
                self.feedback_history[agent_id] = []
            self.feedback_history[agent_id].append(llm_feedback)

            # 3. 개선 완료
            improvement["status"] = ImprovementStatus.COMPLETED
            improvement["progress"] = 100.0
            improvement["completed_at"] = datetime.now()
            improvement["feedback"] = llm_feedback
            improvement["backtest"] = backtest_result

            logger.info(f"개선 완료: {improvement_id} - {agent_id}")

        except Exception as e:
            improvement["status"] = ImprovementStatus.FAILED
            improvement["error"] = str(e)
            logger.error(f"개선 실패: {improvement_id} - {e}")

    async def _run_backtest(
        self,
        agent_id: str,
        strategy_params: Dict[str, Any]
    ) -> BacktestResult:
        """백테스팅 실행"""

        # 실제 백테스팅 엔진과 통합 (현재는 mock 데이터)
        await asyncio.sleep(2)  # 백테스팅 시뮬레이션

        # Mock 백테스팅 결과 생성
        return BacktestResult(
            improvement_id=str(uuid.uuid4()),
            agent_id=agent_id,
            strategy_params=strategy_params,

            # 성과 지표 (mock 데이터)
            total_return=12.5,
            sharpe_ratio=1.8,
            max_drawdown=-8.2,
            win_rate=65.3,
            profit_factor=1.45,

            # Trinity Score 계산
            trinity_score=self._calculate_trinity_score(12.5, 1.8, -8.2),

            # 백테스팅 기간
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now(),
            duration_days=30,

            # 상세 결과
            trades_count=45,
            avg_trade_return=0.28,
            best_trade_return=3.2,
            worst_trade_return=-1.8
        )

    async def _analyze_with_llm(
        self,
        agent_id: str,
        backtest_result: BacktestResult
    ) -> LLMFeedback:
        """LLM으로 백테스팅 결과 분석"""

        # 실제 LLM 통합 (현재는 mock 응답)
        await asyncio.sleep(1)

        # Mock LLM 피드백 생성
        return LLMFeedback(
            improvement_id=str(uuid.uuid4()),
            agent_id=agent_id,

            # 분석 결과
            analysis_summary="현재 전략은 추세 시장에서 잘 작동하지만 횡보 구간에서 손실이 발생합니다.",
            strengths=["강한 추세 포착 능력", "높은 승률"],
            weaknesses=["횡보 시장 적응력 부족", "과도한 거래 빈도"],
            recommendations=[
                "ATR 필터 추가하여 노이즈 거래 감소",
                "횡보 감지 시 포지션 크기 축소"
            ],

            # 파라미터 개선 제안
            parameter_suggestions={
                "atr_filter": {"current": 1.0, "suggested": 1.8, "reason": "노이즈 거래 감소"},
                "min_rr": {"current": 1.2, "suggested": 2.0, "reason": "리스크 대비 수익률 향상"}
            },

            # 예상 개선 효과
            expected_improvement={
                "sharpe_ratio": 2.1,
                "total_return": 15.2,
                "max_drawdown": -6.5
            },
            confidence_score=0.78,

            created_at=datetime.now()
        )

    def _calculate_trinity_score(
        self,
        total_return: float,
        sharpe: float,
        max_drawdown: float
    ) -> float:
        """Trinity Score 계산 (프론트엔드와 동일한 공식)"""
        # 프론트엔드와 동일한 공식 적용
        return (total_return * 0.4) + (sharpe * 25 * 0.35) + ((1 + max(max_drawdown, -0.3)) * 100 * 0.25)

    async def get_latest_backtest(self, agent_id: str) -> Optional[BacktestResult]:
        """에이전트의 최근 백테스팅 결과 조회"""
        # 가장 최근의 백테스팅 결과 찾기
        latest_improvement = None
        for imp_id, imp in self.improvements.items():
            if imp["agent_id"] == agent_id and imp.get("backtest"):
                if latest_improvement is None or imp["created_at"] > latest_improvement["created_at"]:
                    latest_improvement = imp

        return latest_improvement["backtest"] if latest_improvement else None

    async def get_feedback_history(self, agent_id: str) -> List[LLMFeedback]:
        """에이전트의 LLM 피드백 이력 조회"""
        return self.feedback_history.get(agent_id, [])

    async def get_improvement_progress(self) -> Dict[str, Any]:
        """전체 개선 진행 상황 조회"""

        active_improvements = [
            imp for imp in self.improvements.values()
            if imp["status"] in [ImprovementStatus.REQUESTED, ImprovementStatus.BACKTESTING, ImprovementStatus.ANALYZING]
        ]

        completed_count = sum(1 for imp in self.improvements.values()
                            if imp["status"] == ImprovementStatus.COMPLETED)
        failed_count = sum(1 for imp in self.improvements.values()
                         if imp["status"] == ImprovementStatus.FAILED)

        return {
            "active_improvements": len(active_improvements),
            "completed_improvements": completed_count,
            "failed_improvements": failed_count,
            "total_improvements": len(self.improvements),
            "agents": list(set(imp["agent_id"] for imp in self.improvements.values())),
            "latest_improvements": [
                {
                    "agent_id": imp["agent_id"],
                    "status": imp["status"],
                    "progress": imp.get("progress", 0),
                    "created_at": imp["created_at"].isoformat()
                }
                for imp in sorted(
                    self.improvements.values(),
                    key=lambda x: x["created_at"],
                    reverse=True
                )[:5]
            ]
        }

    def initialize_agent_performance(self, agent_id: str, name: str):
        """에이전트 성과 데이터 초기화"""

        # Mock 성과 데이터 생성 (프론트엔드와 동일한 구조)
        self.agent_performance[agent_id] = AgentPerformanceMetrics(
            agent_id=agent_id,
            name=name,

            # 시계열 데이터 (mock)
            score=[100 + i * 0.5 for i in range(96)],
            return_val=[i * 0.1 for i in range(96)],
            sharpe=[1.5 + i * 0.01 for i in range(96)],
            mdd=[-5 - i * 0.05 for i in range(96)],
            win=[60 + i * 0.1 for i in range(96)],

            # 최신 값
            current_score=148.2,
            current_return=9.6,
            current_sharpe=2.41,
            current_mdd=-12.3,
            current_win_rate=67.4,

            # 트레이딩 통계
            total_trades=45,
            winning_trades=30,
            losing_trades=15,
            avg_trade_duration=120.5
        )

    async def get_agent_performance(self, agent_id: str) -> AgentPerformanceMetrics:
        """에이전트별 성과 데이터 제공"""
        if agent_id not in self.agent_performance:
            # 에이전트가 없는 경우 초기화
            agent_names = {
                "momentum_hunter": "MINARA V2",
                "mean_reverter": "ARBITER V1",
                "macro_trader": "NIM-ALPHA",
                "chaos_agent": "CHIMERA-β"
            }
            self.initialize_agent_performance(
                agent_id,
                agent_names.get(agent_id, agent_id)
            )

        return self.agent_performance[agent_id]

    async def get_agent_timeseries(self, agent_id: str, metric: str) -> List[float]:
        """에이전트별 시계열 데이터 제공"""
        if agent_id not in self.agent_performance:
            # 에이전트가 없는 경우 초기화
            agent_names = {
                "momentum_hunter": "MINARA V2",
                "mean_reverter": "ARBITER V1",
                "macro_trader": "NIM-ALPHA",
                "chaos_agent": "CHIMERA-β"
            }
            self.initialize_agent_performance(
                agent_id,
                agent_names.get(agent_id, agent_id)
            )

        performance = self.agent_performance[agent_id]

        # 요청된 메트릭에 해당하는 시계열 데이터 반환
        metric_map = {
            "score": performance.score,
            "return": performance.return_val,
            "sharpe": performance.sharpe,
            "mdd": performance.mdd,
            "win": performance.win
        }

        return metric_map.get(metric, [])

    async def get_dashboard_metrics(self) -> Dict[str, Any]:
        """대시보드용 통합 메트릭 제공"""
        agent_ids = ["momentum_hunter", "mean_reverter", "macro_trader", "chaos_agent"]

        # 모든 에이전트의 성과 데이터 수집
        performances = {}
        for agent_id in agent_ids:
            if agent_id in self.agent_performance:
                performances[agent_id] = self.agent_performance[agent_id]

        if not performances:
            return {"total_agents": 0, "agents": {}, "overall_metrics": {}}

        # 통합 메트릭 계산
        return {
            "total_agents": len(performances),
            "agents": {
                agent_id: {
                    "name": perf.name,
                    "current_score": perf.current_score,
                    "current_return": perf.current_return,
                    "current_sharpe": perf.current_sharpe,
                    "current_mdd": perf.current_mdd,
                    "current_win_rate": perf.current_win_rate
                }
                for agent_id, perf in performances.items()
            },
            "overall_metrics": {
                "avg_trinity_score": sum(p.current_score for p in performances.values()) / len(performances),
                "best_performer": max(performances.values(), key=lambda x: x.current_score).name if performances else "없음",
                "total_trades": sum(p.total_trades for p in performances.values())
            }
        }