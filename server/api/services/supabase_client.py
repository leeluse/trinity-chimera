import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from supabase import create_client, Client
from postgrest import APIError
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env", override=False)

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

    async def get_agent_strategy(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch the currently active strategy code and metadata for an agent.
        """
        try:
            # Get the agent to find the current_strategy_id
            agent_res = self.client.table("agents").select("current_strategy_id").eq("id", agent_id).single().execute()
            agent_data = agent_res.data

            if not agent_data or not agent_data.get("current_strategy_id"):
                return None

            strategy_id = agent_data["current_strategy_id"]

            # Get the strategy details
            strategy_res = self.client.table("strategies").select("*").eq("id", strategy_id).single().execute()
            return strategy_res.data
        except APIError as e:
            print(f"Error fetching agent strategy: {e}")
            return None

    async def save_strategy(self, agent_id: str, code: str, rationale: str, params: Dict[str, Any]) -> Optional[str]:
        """
        Create a new version in strategies table and update the current_strategy_id in the agents table.
        """
        try:
            # 1. Get the current version number for the agent
            version_res = self.client.table("strategies").select("version").eq("agent_id", agent_id).order("version", desc=True).limit(1).execute()
            current_version = 0
            if version_res.data and len(version_res.data) > 0:
                current_version = version_res.data[0]["version"]

            # 2. Insert new strategy version
            new_strategy_data = {
                "agent_id": agent_id,
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
            self.client.table("agents").update({"current_strategy_id": new_strategy_id}).eq("id", agent_id).execute()

            return new_strategy_id
        except APIError as e:
            print(f"Error saving strategy: {e}")
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

    async def save_improvement_log(self, agent_id: str, prev_id: Optional[str], new_id: Optional[str], analysis: str, expected: Dict[str, Any]) -> bool:
        """
        Record the evolution step in improvement_logs.
        """
        try:
            data = {
                "agent_id": agent_id,
                "prev_strategy_id": prev_id,
                "new_strategy_id": new_id,
                "llm_analysis": analysis,
                "expected_improvement": expected
            }
            self.client.table("improvement_logs").insert(data).execute()
            return True
        except APIError as e:
            print(f"Error saving improvement log: {e}")
            return False

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
