import ast
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[3]
WIKI_ROOT = PROJECT_ROOT / "wiki" / "obsidian" / "03_Backend"
MEMORY_DIR = WIKI_ROOT / "Evolution-Memory"


DEFAULT_CONSTITUTION: Dict[str, Any] = {
    "hard_gates": {
        "min_win_rate": 0.45,
        "min_profit_factor": 1.20,
        "min_total_return": 0.00,
        "max_drawdown": 0.25,
        "min_total_trades": 30,
        "min_sharpe_ratio": 0.30,
    },
    "quick_gates": {
        "min_win_rate": 0.38,
        "min_profit_factor": 1.05,
        "min_total_return": -0.02,
        "max_drawdown": 0.35,
        "min_total_trades": 10,
        "min_sharpe_ratio": -0.10,
    },
    "budgets": {
        "max_candidates_per_cycle": 5,
        "max_llm_calls_per_cycle": 5,
    },
    "memory": {
        "recent_failures_for_prompt": 5,
        "recent_successes_for_prompt": 3,
        "dedupe_window": 120,
    },
}


def _utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _sanitize_cell(value: Any) -> str:
    return str(value).replace("|", "/").replace("\n", " ").strip()


class EvolutionWikiMemory:
    def __init__(self):
        self.memory_dir = MEMORY_DIR
        self.constitution_path = self.memory_dir / "Strategy-Constitution.md"
        self.failure_patterns_path = self.memory_dir / "Failure-Patterns.md"
        self.ledger_path = self.memory_dir / "Experiment-Ledger.md"
        self.accepted_path = self.memory_dir / "Accepted-Strategies.md"
        self.state_path = self.memory_dir / "state.json"
        self.ensure_files()

    def ensure_files(self) -> None:
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        if not self.constitution_path.exists():
            config_json = json.dumps(DEFAULT_CONSTITUTION, indent=2, ensure_ascii=False)
            self.constitution_path.write_text(
                "# Strategy Constitution\n\n"
                "진화 후보의 채택/거절 기준입니다. 이 문서는 사람이 읽고 고칠 수 있으며,\n"
                "아래 JSON 블록은 런타임에서 직접 파싱됩니다.\n\n"
                "<!-- CONFIG_START -->\n"
                f"{config_json}\n"
                "<!-- CONFIG_END -->\n",
                encoding="utf-8",
            )
        if not self.failure_patterns_path.exists():
            self.failure_patterns_path.write_text(
                "# Failure Patterns\n\n"
                "반복적으로 실패한 전략 패턴을 누적 기록합니다.\n\n",
                encoding="utf-8",
            )
        if not self.ledger_path.exists():
            self.ledger_path.write_text(
                "# Experiment Ledger\n\n"
                "| time | agent | status | stage | win | pf | ret | mdd | trades | code_hash | reason |\n"
                "|---|---|---|---|---:|---:|---:|---:|---:|---|---|\n",
                encoding="utf-8",
            )
        if not self.accepted_path.exists():
            self.accepted_path.write_text(
                "# Accepted Strategies\n\n"
                "| time | agent | strategy_id | win | pf | ret | mdd | trades | code_hash |\n"
                "|---|---|---|---:|---:|---:|---:|---:|---|\n",
                encoding="utf-8",
            )
        if not self.state_path.exists():
            self.state_path.write_text(
                json.dumps({"experiments": [], "accepted": []}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def load_constitution(self) -> Dict[str, Any]:
        text = self.constitution_path.read_text(encoding="utf-8")
        match = re.search(r"<!-- CONFIG_START -->(.*?)<!-- CONFIG_END -->", text, re.S)
        if not match:
            return json.loads(json.dumps(DEFAULT_CONSTITUTION))
        payload = match.group(1).strip()
        try:
            parsed = json.loads(payload)
        except Exception:
            return json.loads(json.dumps(DEFAULT_CONSTITUTION))

        merged = json.loads(json.dumps(DEFAULT_CONSTITUTION))
        for top_key in ("hard_gates", "quick_gates", "budgets", "memory"):
            value = parsed.get(top_key)
            if isinstance(value, dict):
                merged[top_key].update(value)
        return merged

    def _load_state(self) -> Dict[str, Any]:
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("experiments", [])
                data.setdefault("accepted", [])
                return data
        except Exception:
            pass
        return {"experiments": [], "accepted": []}

    def _save_state(self, state: Dict[str, Any]) -> None:
        # Keep only the latest records for runtime speed.
        state["experiments"] = list(state.get("experiments", []))[-1500:]
        state["accepted"] = list(state.get("accepted", []))[-500:]
        self.state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def compute_fingerprint(self, code: str) -> str:
        code = (code or "").strip()
        if not code:
            return hashlib.sha256(b"").hexdigest()
        try:
            tree = ast.parse(code)
            normalized = ast.dump(tree, include_attributes=False)
            return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        except Exception:
            normalized = re.sub(r"\s+", " ", code)
            return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def is_duplicate(
        self,
        agent_id: str,
        fingerprint: str,
        dedupe_window: int = 120,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        state = self._load_state()
        history = list(state.get("experiments", []))
        checked = 0
        for row in reversed(history):
            if row.get("agent_id") != agent_id:
                continue
            checked += 1
            if row.get("fingerprint") == fingerprint:
                return True, row
            if checked >= max(1, dedupe_window):
                break
        return False, None

    def get_recent_failures(self, agent_id: Optional[str], limit: int = 5) -> List[Dict[str, Any]]:
        state = self._load_state()
        out: List[Dict[str, Any]] = []
        for row in reversed(state.get("experiments", [])):
            if agent_id and row.get("agent_id") != agent_id:
                continue
            status = str(row.get("status") or "")
            if status.startswith("rejected") or status.startswith("error"):
                out.append(row)
            if len(out) >= max(1, limit):
                break
        return out

    def get_recent_successes(self, agent_id: Optional[str], limit: int = 3) -> List[Dict[str, Any]]:
        state = self._load_state()
        out: List[Dict[str, Any]] = []
        for row in reversed(state.get("accepted", [])):
            if agent_id and row.get("agent_id") != agent_id:
                continue
            out.append(row)
            if len(out) >= max(1, limit):
                break
        return out

    def get_agent_attempt_count(self, agent_id: Optional[str]) -> int:
        state = self._load_state()
        if agent_id is None:
            return len(state.get("experiments", []))
        return sum(1 for row in state.get("experiments", []) if row.get("agent_id") == agent_id)

    def build_prompt_context(self, agent_id: Optional[str], constitution: Dict[str, Any]) -> Dict[str, Any]:
        memory_cfg = constitution.get("memory", {})
        fail_limit = int(memory_cfg.get("recent_failures_for_prompt", 5))
        success_limit = int(memory_cfg.get("recent_successes_for_prompt", 3))

        failures = self.get_recent_failures(agent_id, limit=fail_limit)
        successes = self.get_recent_successes(agent_id, limit=success_limit)

        return {
            "hard_gates": constitution.get("hard_gates", {}),
            "recent_failures": failures,
            "recent_successes": successes,
        }

    def log_failure_pattern(
        self,
        agent_id: str,
        reason: str,
        fingerprint: str,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> None:
        metrics = metrics or {}
        line = (
            f"- `{_utc_now()}` [{agent_id}] `{fingerprint[:12]}` "
            f"- reason: {_sanitize_cell(reason)} "
            f"(win={metrics.get('win_rate', 0):.3f}, pf={metrics.get('profit_factor', 0):.3f}, "
            f"ret={metrics.get('total_return', 0):.3f}, mdd={metrics.get('max_drawdown', 0):.3f}, "
            f"trades={metrics.get('total_trades', 0)})\n"
        )
        with self.failure_patterns_path.open("a", encoding="utf-8") as handle:
            handle.write(line)

    def log_experiment(
        self,
        agent_id: str,
        status: str,
        stage: str,
        reason: str,
        fingerprint: str,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        metrics = metrics or {}
        row = {
            "time": _utc_now(),
            "agent_id": agent_id,
            "status": status,
            "stage": stage,
            "reason": reason,
            "fingerprint": fingerprint,
            "metrics": {
                "win_rate": float(metrics.get("win_rate") or 0.0),
                "profit_factor": float(metrics.get("profit_factor") or 0.0),
                "total_return": float(metrics.get("total_return") or 0.0),
                "max_drawdown": float(metrics.get("max_drawdown") or 0.0),
                "total_trades": int(metrics.get("total_trades") or 0),
                "sharpe_ratio": float(metrics.get("sharpe_ratio") or 0.0),
                "trinity_score": float(metrics.get("trinity_score") or 0.0),
            },
        }

        state = self._load_state()
        state.setdefault("experiments", []).append(row)
        self._save_state(state)

        m = row["metrics"]
        line = (
            f"| {row['time']} | {agent_id} | {_sanitize_cell(status)} | {_sanitize_cell(stage)} | "
            f"{m['win_rate']:.3f} | {m['profit_factor']:.3f} | {m['total_return']:.3f} | "
            f"{m['max_drawdown']:.3f} | {m['total_trades']} | {fingerprint[:12]} | {_sanitize_cell(reason)} |\n"
        )
        with self.ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(line)
        return row

    def log_accepted(
        self,
        agent_id: str,
        strategy_id: Optional[str],
        fingerprint: str,
        metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        row = {
            "time": _utc_now(),
            "agent_id": agent_id,
            "strategy_id": strategy_id,
            "fingerprint": fingerprint,
            "metrics": {
                "win_rate": float(metrics.get("win_rate") or 0.0),
                "profit_factor": float(metrics.get("profit_factor") or 0.0),
                "total_return": float(metrics.get("total_return") or 0.0),
                "max_drawdown": float(metrics.get("max_drawdown") or 0.0),
                "total_trades": int(metrics.get("total_trades") or 0),
                "sharpe_ratio": float(metrics.get("sharpe_ratio") or 0.0),
                "trinity_score": float(metrics.get("trinity_score") or 0.0),
            },
        }
        state = self._load_state()
        state.setdefault("accepted", []).append(row)
        self._save_state(state)

        m = row["metrics"]
        line = (
            f"| {row['time']} | {agent_id} | {_sanitize_cell(strategy_id or '-')} | "
            f"{m['win_rate']:.3f} | {m['profit_factor']:.3f} | {m['total_return']:.3f} | "
            f"{m['max_drawdown']:.3f} | {m['total_trades']} | {fingerprint[:12]} |\n"
        )
        with self.accepted_path.open("a", encoding="utf-8") as handle:
            handle.write(line)
        return row
