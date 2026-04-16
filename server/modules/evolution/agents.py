import logging
from enum import Enum
from datetime import datetime
from collections import deque
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class EvolutionState(Enum):
    IDLE = "IDLE"
    TRIGGERED = "TRIGGERED"
    GENERATING = "GENERATING"
    VALIDATING = "VALIDATING"
    COMMITTING = "COMMITTING"

class AgentStateManager:
    """에이전트의 상태, 이름 캐시, 이벤트 로그를 관리하는 클래스"""
    
    def __init__(self, agent_ids: List[str], supabase_manager):
        self.agent_ids = agent_ids
        self.db = supabase_manager
        self._states: Dict[str, EvolutionState] = {aid: EvolutionState.IDLE for aid in agent_ids}
        self._name_cache: Dict[str, str] = {}
        self._event_logs: deque = deque(maxlen=600)
        self._event_seq = 0
        self._latest_improvements: Dict[str, Dict[str, Any]] = {}
        
        # 초기 이름 캐시 로드
        self.refresh_names()

    # -------------------------------------------------------------------------
    # 에이전트 이름 동기화: DB에서 모든 활성 에이전트의 실제 이름을 가져옴
    # -------------------------------------------------------------------------
    def refresh_names(self):
        for aid in self.agent_ids:
            self.resolve_label(aid, force_refresh=True)

    # -------------------------------------------------------------------------
    # 라벨 식별: 에이전트 ID를 사람이 읽기 쉬운 이름(Momentum Hunter 등)으로 변환
    # -------------------------------------------------------------------------
    def resolve_label(self, agent_id: str, force_refresh: bool = False) -> str:
        if not force_refresh and agent_id in self._name_cache:
            return self._name_cache[agent_id]

        # 기본값 설정
        label = str(agent_id).replace("_", " ").title()
        
        try:
            # DB가 연결되어 있으면 실제 이름을 시도
            if hasattr(self.db, "get_agent_info"):
                row = self.db.get_agent_info(agent_id)
                if row and row.get('name'):
                    label = row['name'].strip()
        except Exception as e:
            logger.debug(f"DB Label resolution failed for {agent_id}: {e}")
        
        self._name_cache[agent_id] = label
        return label

    # -------------------------------------------------------------------------
    # 상태 업데이트: 에이전트의 현재 진행 단계(생성 중, 검증 중 등)를 기록
    # -------------------------------------------------------------------------
    def set_state(self, agent_id: str, state: EvolutionState, detail: str = None):
        self._states[agent_id] = state
        
        # 대시보드 표시용 상태 및 진척도 매핑
        mapping = {
            EvolutionState.TRIGGERED: ("triggered", 15),
            EvolutionState.GENERATING: ("generating", 45),
            EvolutionState.VALIDATING: ("backtesting", 75),
            EvolutionState.COMMITTING: ("committing", 90),
            EvolutionState.IDLE: ("idle", 0),
        }
        status, progress = mapping.get(state, ("idle", 0))
        
        self._latest_improvements[agent_id] = {
            "agent_id": agent_id,
            "status": status,
            "progress": progress,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "detail": detail
        }
        
        if state != EvolutionState.IDLE:
            msg = f"[{self.resolve_label(agent_id)}] {detail or state.value}"
            self.add_event("info", status, msg, agent_id)

    def get_state(self, agent_id: str) -> EvolutionState:
        return self._states.get(agent_id, EvolutionState.IDLE)

    # -------------------------------------------------------------------------
    # 이벤트 로그 추가: 대시보드 하단 로그 패널에 표시될 새로운 메시지 추가
    # -------------------------------------------------------------------------
    def add_event(
        self,
        level: str,
        phase: str,
        message: str,
        agent_id: str = None,
        meta: Optional[Dict[str, Any]] = None,
    ):
        self._event_seq += 1
        self._event_logs.append({
            "id": self._event_seq,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "phase": phase,
            "message": message,
            "agent_id": agent_id,
            "agent_label": self.resolve_label(agent_id) if agent_id else None,
            "meta": meta or {},
        })

    # -------------------------------------------------------------------------
    # 데이터 스냅샷: 현재 모든 에이전트의 상태와 진행도를 한눈에 보여주는 요약 생성
    # -------------------------------------------------------------------------
    def get_snapshot(self) -> Dict[str, Any]:
        latest = [self._latest_improvements.get(aid, {"agent_id": aid, "status": "idle", "progress": 0}) 
                  for aid in self.agent_ids]
        
        return {
            "active_improvements": sum(1 for i in latest if i["status"] not in ["idle", "completed", "failed"]),
            "agents": self.agent_ids,
            "latest_improvements": latest
        }

    def get_events(self, limit: int = 120, agent_id: str = None) -> List[Dict[str, Any]]:
        logs = list(self._event_logs)
        if agent_id:
            logs = [e for e in logs if e["agent_id"] == agent_id]
        logs.reverse()
        return logs[:limit]
