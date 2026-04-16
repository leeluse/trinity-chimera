import os
import uuid
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional
from supabase import create_client, Client
from postgrest import APIError
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env", override=False)

logger = logging.getLogger(__name__)

class SupabaseManager:
    """
    Manager for interacting with the Supabase backend for the Trinity Autonomous Evolution System.
    Handles strategy versioning, backtest results, and improvement logging.
    """
    def __init__(self):
        url: Optional[str] = os.environ.get("SUPABASE_URL")
        key: Optional[str] = os.environ.get("SUPABASE_KEY")

        if not url or not key:
            raise EnvironmentError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables.")

        self.client: Client = create_client(url, key)

    @staticmethod
    def _is_uuid_like(value: str) -> bool:
        try:
            uuid.UUID(str(value))
            return True
        except (ValueError, TypeError):
            return False

    def _resolve_agent_row(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Resolve both UUID agent ids and technical aliases like momentum_hunter.
        """
        alias_hints: Dict[str, List[str]] = {
            "momentum_hunter": ["momentum", "hunter"],
            "mean_reverter": ["mean", "revert"],
            "macro_trader": ["macro", "trend"],
            "chaos_agent": ["chaos", "scalp"],
        }

        try:
            if self._is_uuid_like(agent_id):
                res = self.client.table("agents").select("id,name,current_strategy_id").eq("id", agent_id).limit(1).execute()
                rows = res.data or []
                if rows:
                    return rows[0]

            # Exact name match first
            name_res = self.client.table("agents").select("id,name,current_strategy_id").eq("name", agent_id).limit(1).execute()
            name_rows = name_res.data or []
            if name_rows:
                return name_rows[0]

            # Heuristic alias matching against name
            for hint in alias_hints.get(agent_id, [agent_id]):
                res = self.client.table("agents").select("id,name,current_strategy_id").ilike("name", f"%{hint}%").limit(1).execute()
                rows = res.data or []
                if rows:
                    return rows[0]
        except APIError as e:
            print(f"Error resolving agent row ({agent_id}): {e}")
            return None

        return None

    async def get_agent_strategy(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch the currently active strategy code and metadata for an agent.
        """
        try:
            agent_data = self._resolve_agent_row(agent_id)

            if not agent_data:
                return None

            strategy_id = agent_data.get("current_strategy_id")
            if strategy_id:
                strategy_res = self.client.table("strategies").select("*").eq("id", strategy_id).single().execute()
                return strategy_res.data

            # Fallback 1: latest strategy owned by this agent
            own_rows = (
                self.client.table("strategies")
                .select("*")
                .eq("agent_id", agent_data["id"])
                .order("version", desc=True)
                .limit(1)
                .execute()
                .data
                or []
            )
            if own_rows:
                return own_rows[0]

            # Fallback 2: latest system strategy from catalog agent
            system_agent_rows = (
                self.client.table("agents")
                .select("id")
                .eq("name", "system_strategy_catalog")
                .limit(1)
                .execute()
                .data
                or []
            )
            if not system_agent_rows:
                return None

            system_agent_id = system_agent_rows[0]["id"]
            system_rows = (
                self.client.table("strategies")
                .select("*")
                .eq("agent_id", system_agent_id)
                .order("version", desc=True)
                .limit(1)
                .execute()
                .data
                or []
            )
            return system_rows[0] if system_rows else None
        except APIError as e:
            print(f"Error fetching agent strategy: {e}")
            return None

    async def save_strategy(self, agent_id: str, code: str, rationale: str, params: Dict[str, Any]) -> Optional[str]:
        """
        Create a new version in strategies table and update the current_strategy_id in the agents table.
        """
        try:
            resolved_agent = self._resolve_agent_row(agent_id)
            if not resolved_agent:
                print(f"Error saving strategy: agent not found for {agent_id}")
                return None
            resolved_agent_id = resolved_agent["id"]

            # 1. Get the current version number for the agent
            version_res = self.client.table("strategies").select("version").eq("agent_id", resolved_agent_id).order("version", desc=True).limit(1).execute()
            current_version = 0
            if version_res.data and len(version_res.data) > 0:
                current_version = version_res.data[0]["version"]

            # 2. Insert new strategy version
            new_strategy_data = {
                "agent_id": resolved_agent_id,
                "version": current_version + 1,
                "code": code,
                "rationale": rationale,
                "params": params
            }
            strategy_res = self.client.table("strategies").insert(
                new_strategy_data,
                returning="representation",
            ).execute()
            rows = strategy_res.data or []
            if not rows:
                return None
            new_strategy_id = rows[0]["id"]

            # 3. Update agents table to point to the new strategy
            self.client.table("agents").update({"current_strategy_id": new_strategy_id}).eq("id", resolved_agent_id).execute()

            return new_strategy_id
        except APIError as e:
            print(f"Error saving strategy: {e}")
            return None

    async def get_backtest_for_period(
        self,
        strategy_id: str,
        end_date: Optional[datetime] = None,
        period_type: str = "OOS"
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch the latest backtest metrics for a strategy up to end_date.
        """
        try:
            query = self.client.table("backtest_results").select(
                "trinity_score,return_val,sharpe,mdd,win_rate,test_period,created_at"
            ).eq("strategy_id", strategy_id)

            if end_date is not None:
                end_iso = end_date.isoformat() if hasattr(end_date, "isoformat") else str(end_date)
                query = query.lte("created_at", end_iso)

            rows = query.order("created_at", desc=True).limit(20).execute().data or []
            if not rows:
                return None

            selected = rows[0]
            if period_type:
                for row in rows:
                    test_period = row.get("test_period") or {}
                    if isinstance(test_period, dict) and str(test_period.get("type", "")).upper() == period_type.upper():
                        selected = row
                        break

            return {
                "trinity_score": selected.get("trinity_score"),
                "return": selected.get("return_val"),
                "sharpe": selected.get("sharpe"),
                "mdd": selected.get("mdd"),
                "win_rate": selected.get("win_rate"),
                "profit_factor": selected.get("profit_factor", 0.0),
                "test_period": selected.get("test_period") or {},
            }
        except APIError as e:
            print(f"Error fetching backtest period: {e}")
            return None

    async def save_backtest(self, strategy_id: str, metrics: Dict[str, Any]) -> bool:
        """
        Insert results (Trinity Score, etc.) into backtest_results.
        """
        try:
            # Mapping provided metrics to schema columns
            data = {
                "strategy_id": strategy_id,
                "trinity_score": metrics.get("trinity_score"),
                "return_val": metrics.get("return"),
                "sharpe": metrics.get("sharpe"),
                "mdd": metrics.get("mdd"),
                "win_rate": metrics.get("win_rate"),
                "test_period": metrics.get("test_period", {})
            }
            self.client.table("backtest_results").insert(data).execute()
            return True
        except APIError as e:
            print(f"Error saving backtest: {e}")
            return False

    async def save_evolution_log(self, agent_id: str, model_id: str, cost: float, tokens_prompt: int, tokens_completion: int, duration: float, status: str, error: Optional[str] = None) -> bool:
        """
        Record LLM usage and cost for the evolution process in evolution_logs table.
        """
        try:
            resolved_agent = self._resolve_agent_row(agent_id)
            if not resolved_agent:
                print(f"Error saving evolution log: agent not found for {agent_id}")
                return False

            data = {
                "agent_id": resolved_agent["id"],
                "model_id": model_id,
                "cost": cost,
                "tokens_prompt": tokens_prompt,
                "tokens_completion": tokens_completion,
                "duration": duration,
                "status": status,
                "error": error
            }
            self.client.table("evolution_logs").insert(data).execute()
            return True
        except APIError as e:
            print(f"Error saving evolution log: {e}")
            return False

    async def save_improvement_log(self, agent_id: str, prev_id: Optional[str], new_id: Optional[str], analysis: str, expected: Dict[str, Any]) -> bool:
        """
        Record the evolution step in improvement_logs.
        """
        try:
            resolved_agent = self._resolve_agent_row(agent_id)
            if not resolved_agent:
                print(f"Error saving improvement log: agent not found for {agent_id}")
                return False

            expected_payload = expected if isinstance(expected, dict) else {}
            expected_payload = dict(expected_payload)
            decision_payload = expected_payload.get("decision")
            if not isinstance(decision_payload, dict):
                decision_payload = {}
            decision_payload.setdefault("agent_alias", agent_id)
            if new_id and not decision_payload.get("result"):
                decision_payload["result"] = "accepted"
            expected_payload["decision"] = decision_payload

            data = {
                "agent_id": resolved_agent["id"],
                "prev_strategy_id": prev_id,
                "new_strategy_id": new_id,
                "llm_analysis": analysis,
                "expected_improvement": expected_payload
            }
            self.client.table("improvement_logs").insert(data).execute()
            return True
        except APIError as e:
            print(f"Error saving improvement log: {e}")
            return False

    async def list_improvement_logs(
        self,
        limit: int = 200,
        agent_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent improvement_logs in descending order.
        """
        try:
            query = (
                self.client.table("improvement_logs")
                .select("id,agent_id,prev_strategy_id,new_strategy_id,llm_analysis,expected_improvement,created_at")
                .order("created_at", desc=True)
                .limit(max(1, min(limit, 1000)))
            )

            if agent_id:
                resolved_agent = self._resolve_agent_row(agent_id)
                if resolved_agent and resolved_agent.get("id"):
                    query = query.eq("agent_id", resolved_agent["id"])
                elif self._is_uuid_like(agent_id):
                    query = query.eq("agent_id", agent_id)

            res = query.execute()
            return res.data or []
        except APIError as e:
            print(f"Error listing improvement logs: {e}")
            return []

    def get_agent_name_map(self, agent_ids: List[str]) -> Dict[str, str]:
        """
        Build {agent_uuid: agent_name} map for the given agent ids.
        """
        unique_ids = []
        for agent_id in agent_ids:
            if not agent_id:
                continue
            if agent_id not in unique_ids:
                unique_ids.append(agent_id)

        if not unique_ids:
            return {}

        try:
            res = (
                self.client.table("agents")
                .select("id,name")
                .in_("id", unique_ids)
                .execute()
            )
            rows = res.data or []
            return {
                str(row.get("id")): str(row.get("name") or row.get("id"))
                for row in rows
                if row.get("id")
            }
        except APIError as e:
            print(f"Error fetching agent name map: {e}")
            return {}

    async def get_all_agent_scores(self) -> List[Dict[str, Any]]:
        """
        모든 에이전트의 최신 Trinity Score를 가져와 CompetitiveRankCalculator에 전달.
        Returns: [{"agent_id": str, "score": float}, ...]
        """
        try:
            # agents 테이블에서 모든 활성 에이전트 조회
            agents_res = (
                self.client.table("agents")
                .select("id,name,current_strategy_id")
                .eq("status", "ACTIVE")
                .execute()
            )
            agents = agents_res.data or []
            result = []

            for agent in agents:
                agent_uuid = agent.get("id")
                strategy_id = agent.get("current_strategy_id")
                if not strategy_id:
                    continue

                # 해당 전략의 최신 backtest 결과에서 trinity_score 조회
                bt_res = (
                    self.client.table("backtest_results")
                    .select("trinity_score")
                    .eq("strategy_id", strategy_id)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                bt_rows = bt_res.data or []
                score = float(bt_rows[0].get("trinity_score") or 0.0) if bt_rows else 0.0

                result.append({
                    "agent_id": agent.get("name") or agent_uuid,
                    "score": score,
                })

            return result
        except APIError as e:
            print(f"Error fetching all agent scores: {e}")
            return []



    # -----------------------------
    # Strategy DB helper methods
    # -----------------------------
    def list_strategies(self, source: Optional[str] = None, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Fetch strategies rows (optionally filtered by source), newest first.
        """
        try:
            query = self.client.table("strategies").select("*").order("created_at", desc=True).limit(limit)
            if source:
                query = query.eq("source", source)
            res = query.execute()
            return res.data or []
        except APIError as e:
            print(f"Error listing strategies: {e}")
            return []

    def get_strategy_by_key(self, strategy_key: str, source: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Find latest strategy row by params.strategy_key.
        """
        rows = self.list_strategies(source=source)
        for row in rows:
            params = row.get("params") or {}
            if not isinstance(params, dict):
                continue
            if params.get("strategy_key") == strategy_key:
                return row
        return None

    def save_system_strategy(
        self,
        strategy_key: str,
        code: str,
        params: Dict[str, Any],
        rationale: str = "Seeded from local strategy catalog",
        name: Optional[str] = None
    ) -> Optional[str]:
        """
        Insert a system strategy if it does not already exist by params.strategy_key.
        Returns strategy id.
        """
        try:
            existing = self.get_strategy_by_key(strategy_key=strategy_key, source="system")
            if existing:
                return existing.get("id")

            system_agent_id = self.ensure_system_agent()
            if not system_agent_id:
                return None

            next_version = self.get_next_strategy_version(system_agent_id)

            data = {
                "agent_id": system_agent_id,
                "version": next_version,
                "code": code,
                "name": name or strategy_key,
                "params": params,
                "rationale": rationale,
                "source": "system",
            }
            res = self.client.table("strategies").insert(
                data,
                returning="representation",
            ).execute()
            rows = res.data or []
            if not rows:
                return None
            return rows[0].get("id")
        except APIError as e:
            print(f"Error saving system strategy {strategy_key}: {e}")
            return None

    def get_next_strategy_version(self, agent_id: str) -> int:
        """
        Return next strategy version for a given agent.
        """
        try:
            res = self.client.table("strategies").select("version").eq("agent_id", agent_id).order("version", desc=True).limit(1).execute()
            rows = res.data or []
            if not rows:
                return 1
            return int(rows[0].get("version") or 0) + 1
        except APIError as e:
            print(f"Error getting next strategy version for {agent_id}: {e}")
            return 1

    def ensure_system_agent(self) -> Optional[str]:
        """
        Ensure there is an internal 'system' agent row used to own system strategies.
        """
        try:
            name = "system_strategy_catalog"
            existing = self.client.table("agents").select("id").eq("name", name).limit(1).execute()
            rows = existing.data or []
            if rows:
                return rows[0].get("id")

            payload = {
                "name": name,
                "persona": "system",
                "status": "ACTIVE",
            }
            created = self.client.table("agents").insert(payload, returning="representation").execute()
            created_rows = created.data or []
            if not created_rows:
                return None
            return created_rows[0].get("id")
        except APIError as e:
            print(f"Error ensuring system agent: {e}")
            return None

    # -----------------------------
    # Chat History methods
    # -----------------------------
    async def save_chat_message(
        self, 
        session_id: str, 
        role: str, 
        content: str, 
        msg_type: str = "text", 
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Save a chat message to Supabase.
        """
        try:
            payload = {
                "session_id": session_id,
                "role": role,
                "content": content,
                "type": msg_type,
                "data": data or {}
            }
            self.client.table("chat_messages").insert(payload).execute()
            return True
        except Exception as e:
            logger.error("Error saving chat message: %s", e)
            return False

    async def get_chat_history(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch chat history for a given session.
        """
        try:
            res = (
                self.client.table("chat_messages")
                .select("*")
                .eq("session_id", session_id)
                .order("created_at", desc=False) # 오래된 순서대로 (대화 흐름)
                .limit(limit)
                .execute()
            )
            return res.data or []
        except Exception as e:
            logger.error("Error fetching chat history: %s", e)
            return []
