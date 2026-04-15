import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional

from server.shared.db.supabase import SupabaseManager
from server.modules.evolution.trigger import EvolutionTrigger
from server.modules.evolution.constants import AGENT_IDS
from server.modules.evolution.llm import EvolutionLLM
from server.modules.evolution.agents import AgentStateManager, EvolutionState
from server.modules.evolution.scoring import calculate_trinity_score, evaluate_improvement
from server.modules.backtest.evolution.evolution_engine import EvolutionEngine

logger = logging.getLogger(__name__)

class EvolutionOrchestrator:
    # -------------------------------------------------------------------------
    # 시스템 초기화: DB 연결, LLM 클라이언트 및 에이전트 상태 관리자 생성
    # -------------------------------------------------------------------------
    def __init__(self):
        self.db = SupabaseManager()
        self.llm = EvolutionLLM()
        self.trigger_engine = EvolutionTrigger()
        self.agent_manager = AgentStateManager(list(AGENT_IDS), self.db)
        self.engine = EvolutionEngine()
        
        # 성과 요약 통계
        self.stats = {
            "total": 0,
            "completed": 0,
            "failed": 0
        }

    # -------------------------------------------------------------------------
    # 진화 한 주기 실행: 단일 에이전트의 트리거 확인부터 전략 반영까지 전체 수행
    # -------------------------------------------------------------------------
    async def run_evolution_cycle(self, agent_id: str, force: bool = False):
        """특정 에이전트의 1회 진화 사이클 실행"""
        label = self.agent_manager.resolve_label(agent_id)
        
        # 1. 트리거 체크
        if not force and not await self.trigger_engine.check_trigger(agent_id):
            logger.info(f"[{label}] 트리거 미충족, 스킵합니다.")
            return

        self.stats["total"] += 1
        self.agent_manager.set_state(agent_id, EvolutionState.TRIGGERED)

        try:
            # 2. 현재 전략 및 마켓 데이터 준비
            self.agent_manager.set_state(agent_id, EvolutionState.GENERATING, "기본 정보 및 마켓 레짐 분석 중")
            strategy_data = await self.db.get_agent_strategy(agent_id)
            if not strategy_data:
                raise ValueError("현재 활성 전략을 찾을 수 없습니다.")

            # 3. LLM을 통한 후보 전략 생성 (새 모듈 호출)
            evolution_package = self._build_evolution_package(agent_id, strategy_data)
            new_code = await self.llm.generate_improved_code(evolution_package)
            
            if not new_code:
                raise ValueError("LLM이 유효한 코드를 생성하지 못했습니다.")

            # 4. 후보 전략 검증 (백테스트)
            self.agent_manager.set_state(agent_id, EvolutionState.VALIDATING, "후보 전략 OOS 백테스트 진행 중")
            bt_res = await self.engine.run(new_code, agent_id, {"agent_id": agent_id})
            
            if not bt_res.get("success"):
                raise ValueError(f"백테스트 검증 실패: {bt_res.get('error')}")

            # 5. 채택 여부 결정 (Scoring)
            candidate_metrics = bt_res["metrics"]
            baseline_metrics = strategy_data.get("metrics", {}) # 실제로는 과거 백테스트 결과에서 가져와야 함
            
            is_improved = evaluate_improvement(baseline_metrics, candidate_metrics)
            
            if is_improved:
                self.agent_manager.set_state(agent_id, EvolutionState.COMMITTING, "개선 확인! 새 전략 반영 중")
                # DB 저장 로직 (생략 - 기존 로직 참고)
                # ...
                self.stats["completed"] += 1
                self.agent_manager.add_event("success", "completed", f"[{label}] 진화 성공!", agent_id)
            else:
                self.agent_manager.add_event("warning", "rejected", f"[{label}] 개선 실패 (성능 미달)", agent_id)

        except Exception as e:
            logger.exception(f"[{label}] 진화 루프 중 에러 발생")
            self.stats["failed"] += 1
            self.agent_manager.add_event("error", "failed", f"[{label}] 에러: {str(e)}", agent_id)
        finally:
            self.agent_manager.set_state(agent_id, EvolutionState.IDLE)

    # -------------------------------------------------------------------------
    # 진화 데이터 패키징: LLM에게 현재 전략과 성과 지표를 묶어 전달
    # -------------------------------------------------------------------------
    def _build_evolution_package(self, agent_id: str, strategy_data: Dict[str, Any]) -> Dict[str, Any]:
        """LLM에게 보낼 패키지 구성"""
        return {
            "current_strategy_code": strategy_data.get("code", ""),
            "metrics": strategy_data.get("metrics", {}),
            "agent_id": agent_id
        }

    # -------------------------------------------------------------------------
    # 대시보드 상태 요약: 모든 에이전트의 현재 진척도와 성공/실패 통계 반환
    # -------------------------------------------------------------------------
    def get_dashboard_snapshot(self) -> Dict[str, Any]:
        """UI 대시보드 상단 요약용 데이터 (전체 스냅샷)"""
        snapshot = self.agent_manager.get_snapshot()
        return {
            "total_improvements": self.stats["total"],
            "completed_improvements": self.stats["completed"],
            "failed_improvements": self.stats["failed"],
            "active_improvements": snapshot.get("active_improvements", 0),
            "latest_improvements": snapshot.get("latest_improvements", [])
        }

    def get_evolution_events(self, limit: int = 120, agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """시스템 이벤트 로그 조회"""
        # AgentStateManager에 이벤트 리스트가 있다고 가정하거나 빈 리스트 반환
        if hasattr(self.agent_manager, "get_events"):
            return self.agent_manager.get_events(limit=limit, agent_id=agent_id)
        return []

# 싱글톤 인스턴스 관리
_orchestrator = None
def get_evolution_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = EvolutionOrchestrator()
    return _orchestrator
