from __future__ import annotations

import asyncio
import copy
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[3]
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.isoformat()


def _sanitize_log_line(raw: str) -> str:
    text = str(raw or "")
    if not text:
        return ""
    # Keep only printable text + whitespace used for line separation.
    return _CONTROL_CHARS.sub("", text).strip()


def _is_litellm_reachable() -> bool:
    provider = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    if provider != "litellm":
        return False

    base = (os.getenv("LITELLM_BASE_URL") or "").strip().rstrip("/")
    if not base:
        return False
    if not base.startswith("http://") and not base.startswith("https://"):
        base = f"http://{base}"

    probe_url = f"{base}/models"
    req = urllib.request.Request(probe_url, method="GET")
    api_key = (os.getenv("LITELLM_API_KEY") or "").strip()
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            status = int(getattr(resp, "status", 0) or 0)
            return 200 <= status < 500
    except urllib.error.HTTPError as e:
        # 401/403/404는 "도달 가능하지만 인증/경로 이슈"이므로 unreachable로 보지 않는다.
        code = int(getattr(e, "code", 0) or 0)
        return 400 <= code < 500
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


@dataclass
class LlmLoopAutomationConfig:
    symbol: str = "BTCUSDT"
    timeframe: str = "15m"
    regime_timeframe: str = "1h"
    start_date: str = "2021-01-01"
    end_date: str = "2026-01-31"
    strategies: List[str] = field(
        default_factory=lambda: [
            "Bull Strategy 01",
            "Bull Strategy 02",
            "Bull Strategy 03",
            "Bull Strategy 04",
        ]
    )
    iterations: int = 1
    interval_minutes: int = 5
    fallback_minutes: int = 30
    apply_best_db: bool = True
    parallel_strategies: int = 2


class LlmLoopAutomationService:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._task: Optional[asyncio.Task] = None
        self._active_procs: List[asyncio.subprocess.Process] = []

        self.enabled: bool = False
        self.running: bool = False
        self.config = LlmLoopAutomationConfig()

        self.next_run_at: Optional[datetime] = None
        self.last_started_at: Optional[datetime] = None
        self.last_finished_at: Optional[datetime] = None

        self.last_success: Optional[bool] = None
        self.last_error: str = ""
        self.last_summary_path: str = ""
        self.last_stdout_tail: str = ""
        self.current_stdout_tail: str = ""
        self.last_run_improved: Optional[bool] = None
        self.last_improved_count: int = 0
        self.last_strategy_count: int = 0

        self.total_runs: int = 0
        self.success_runs: int = 0
        self.failed_runs: int = 0
        self.improved_runs: int = 0
        self._strategy_cursor: int = 0
        self._timeout_streak: int = 0

    async def start(self, cfg: Optional[LlmLoopAutomationConfig] = None, run_immediately: bool = True) -> Dict[str, Any]:
        async with self._lock:
            if cfg is not None:
                self.config = copy.deepcopy(cfg)
            self.enabled = True
            self.current_stdout_tail = ""
            self._strategy_cursor = 0
            self.next_run_at = _utcnow() if run_immediately else (_utcnow() + timedelta(minutes=self.config.interval_minutes))
            if self._task is None or self._task.done():
                self._task = asyncio.create_task(self._runner(), name="llm_loop_automation_runner")
            return self._snapshot_unlocked()

    async def stop(self, terminate_running: bool = True) -> Dict[str, Any]:
        procs: List[asyncio.subprocess.Process] = []
        async with self._lock:
            self.enabled = False
            self.next_run_at = None
            if terminate_running:
                procs = list(self._active_procs)

        for proc in procs:
            if proc.returncode is not None:
                continue
            try:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=8)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

        async with self._lock:
            return self._snapshot_unlocked()

    async def trigger_now(self) -> Dict[str, Any]:
        async with self._lock:
            self.next_run_at = _utcnow()
            if self.enabled and (self._task is None or self._task.done()):
                self._task = asyncio.create_task(self._runner(), name="llm_loop_automation_runner")
            return self._snapshot_unlocked()

    async def status(self) -> Dict[str, Any]:
        async with self._lock:
            return self._snapshot_unlocked()

    def _snapshot_unlocked(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "running": self.running,
            "config": {
                "symbol": self.config.symbol,
                "timeframe": self.config.timeframe,
                "regime_timeframe": self.config.regime_timeframe,
                "start_date": self.config.start_date,
                "end_date": self.config.end_date,
                "strategies": list(self.config.strategies),
                "iterations": int(self.config.iterations),
                "interval_minutes": int(self.config.interval_minutes),
                "fallback_minutes": int(self.config.fallback_minutes),
                "apply_best_db": bool(self.config.apply_best_db),
                "parallel_strategies": int(self.config.parallel_strategies),
            },
            "next_run_at": _iso(self.next_run_at),
            "last_started_at": _iso(self.last_started_at),
            "last_finished_at": _iso(self.last_finished_at),
            "last_success": self.last_success,
            "last_error": self.last_error,
            "last_summary_path": self.last_summary_path,
            "last_stdout_tail": self.last_stdout_tail,
            "current_stdout_tail": self.current_stdout_tail,
            "last_run_improved": self.last_run_improved,
            "last_improved_count": self.last_improved_count,
            "last_strategy_count": self.last_strategy_count,
            "total_runs": self.total_runs,
            "success_runs": self.success_runs,
            "failed_runs": self.failed_runs,
            "improved_runs": self.improved_runs,
            "timeout_streak": self._timeout_streak,
        }

    async def _runner(self) -> None:
        while True:
            async with self._lock:
                if not self.enabled:
                    self.running = False
                    self._active_procs = []
                    return
                due_at = self.next_run_at or _utcnow()

            wait_sec = (due_at - _utcnow()).total_seconds()
            if wait_sec > 0:
                await asyncio.sleep(min(wait_sec, 2.0))
                continue

            result = await self._run_once()
            ok = bool(result.get("success"))

            async with self._lock:
                if self.enabled:
                    interval = self.config.interval_minutes if ok else self.config.fallback_minutes
                    self.next_run_at = _utcnow() + timedelta(minutes=max(1, int(interval)))

    async def _run_once(self) -> Dict[str, Any]:
        cfg = None
        async with self._lock:
            if self.running:
                return {"success": False, "error": "already running"}
            self.running = True
            self.last_started_at = _utcnow()
            self.last_error = ""
            cfg = copy.deepcopy(self.config)

        script_path = PROJECT_ROOT / "scripts" / "llm_refactor_regime_loop.py"
        out_dir = PROJECT_ROOT / "tmp" / "llm_regime_loop_auto"
        out_dir.mkdir(parents=True, exist_ok=True)
        cache_path = PROJECT_ROOT / "tmp" / "cache" / "ohlcv" / (
            f"{cfg.symbol}_{cfg.timeframe}_{cfg.start_date}_{cfg.end_date}.parquet"
        )

        cmd = [
            sys.executable,
            "-u",
            str(script_path),
            "--source", "db",
            "--symbol", cfg.symbol,
            "--timeframe", cfg.timeframe,
            "--regime-timeframe", cfg.regime_timeframe,
            "--start", cfg.start_date,
            "--end", cfg.end_date,
            "--iterations", str(max(0, int(cfg.iterations))),
            "--max-tokens", os.environ.get("LLM_REFACTOR_MAX_TOKENS", "1200"),
            "--prompt-code-max-chars", os.environ.get("LLM_REFACTOR_PROMPT_CODE_MAX_CHARS", "6000"),
            "--mutation-candidates", os.environ.get("LLM_REFACTOR_MUTATION_CANDIDATES", "12"),
            "--micro-segments", os.environ.get("LLM_REFACTOR_MICRO_SEGMENTS", "3"),
            "--micro-max-bars", os.environ.get("LLM_REFACTOR_MICRO_MAX_BARS", "5000"),
            "--full-candidates", os.environ.get("LLM_REFACTOR_FULL_CANDIDATES", "2"),
        ]
        run_strategies = list(cfg.strategies)
        effective_parallel = max(1, int(cfg.parallel_strategies or 1))
        if self._timeout_streak > 0:
            effective_parallel = 1
        if run_strategies:
            # 병렬 배치: 자동화 1회 실행당 전략 N개를 순환 선택
            batch_size = effective_parallel
            batch_size = min(batch_size, len(run_strategies))
            selected: List[str] = []
            for _ in range(batch_size):
                idx = self._strategy_cursor % len(run_strategies)
                selected.append(run_strategies[idx])
                self._strategy_cursor = (idx + 1) % len(run_strategies)
            run_strategies = selected

        stdout_text = ""
        stderr_text = ""
        return_code = 0
        summary_paths: List[str] = []
        improved_count_total = 0
        strategy_count_total = 0
        timeout_hits_total = 0
        all_lines: List[str] = []

        async def _push_line(line: str) -> None:
            safe_line = _sanitize_log_line(line)
            if not safe_line:
                return
            all_lines.append(safe_line)
            tail = "\n".join(all_lines[-120:])
            async with self._lock:
                self.current_stdout_tail = tail

        if run_strategies:
            await _push_line(
                f"[batch] parallel={effective_parallel} "
                f"strategies={', '.join(run_strategies)}"
            )
            if self._timeout_streak > 0 and effective_parallel == 1:
                await _push_line("[batch] timeout detected previously -> temporary serial mode")

        async def _pump_stream(
            stream: Optional[asyncio.StreamReader],
            tag: str,
            label: str,
            sink: List[str],
        ) -> str:
            if stream is None:
                return ""
            buf_lines: List[str] = []
            while True:
                raw = await stream.readline()
                if not raw:
                    break
                txt = _sanitize_log_line(raw.decode("utf-8", errors="ignore"))
                if not txt:
                    continue
                buf_lines.append(txt)
                sink.append(txt)
                prefix = f"[{label}] "
                if tag == "stderr":
                    lower = txt.lower()
                    if "apitimeouterror" in lower or "request timed out" in lower:
                        await _push_line(prefix + "[retry] LLM timeout -> fallback model retry")
                        continue
                    if "litellm.info" in lower or "give feedback / get help" in lower:
                        continue
                    await _push_line(prefix + f"[stderr] {txt}")
                else:
                    await _push_line(prefix + txt)
            return "\n".join(buf_lines)

        def _safe_key(text: str) -> str:
            return re.sub(r"[^A-Za-z0-9_]+", "_", str(text)).strip("_") or "strategy"

        async def _run_strategy(strategy_name: str) -> Dict[str, Any]:
            local_lines: List[str] = []
            label = _safe_key(strategy_name).replace("Bull_Strategy_", "B")
            strategy_out_dir = out_dir / _safe_key(strategy_name)
            strategy_out_dir.mkdir(parents=True, exist_ok=True)

            strategy_cmd = list(cmd)
            strategy_cmd.extend(["--out-dir", str(strategy_out_dir.relative_to(PROJECT_ROOT))])
            strategy_cmd.extend(["--strategies", strategy_name])
            if cfg.apply_best_db:
                strategy_cmd.append("--apply-best-db")
            if cache_path.exists():
                strategy_cmd.extend(["--ohlcv-cache", str(cache_path.relative_to(PROJECT_ROOT))])

            proc: Optional[asyncio.subprocess.Process] = None
            local_stdout = ""
            local_stderr = ""
            rc = -1
            summary_path = ""
            improved_count = 0
            strategy_count = 0
            timeout_hits = 0
            try:
                child_env = os.environ.copy()
                litellm_up = _is_litellm_reachable()
                if litellm_up:
                    await _push_line(f"[{label}] [info] LiteLLM reachable")
                else:
                    await _push_line(f"[{label}] [warn] LiteLLM unreachable")

                # 운영 정책: Ollama fallback 비활성화 (LiteLLM만 사용)
                child_env["LLM_ENABLE_OLLAMA_FALLBACK"] = "0"
                child_env["LLM_REFACTOR_DISABLE_OLLAMA_FALLBACK"] = "1"
                # 타임아웃: env 설정 우선, 없으면 45s
                child_env["LLM_REFACTOR_TIMEOUT_SECONDS"] = os.environ.get("LLM_REFACTOR_TIMEOUT_SECONDS", "45")
                # 모델 체인: env 설정 우선, 없으면 CODE_GEN_MODEL → CODE_GEN_FALLBACK_MODEL 순으로 사용
                _primary = os.environ.get("CODE_GEN_MODEL") or os.environ.get("LITELLM_MODEL") or ""
                _fallback = os.environ.get("CODE_GEN_FALLBACK_MODEL") or ""
                _model_chain = ",".join(m for m in [_primary, _fallback] if m)
                child_env["LLM_REFACTOR_FALLBACK_MODELS"] = os.environ.get("LLM_REFACTOR_FALLBACK_MODELS") or _model_chain or "deepseek-v4-pro"
                # LiteLLM이 죽어 있으면 failover 대기를 길게 끌지 않음.
                default_failover = "12" if litellm_up else "8"
                child_env["LITELLM_FAILOVER_TIMEOUT"] = os.environ.get("LITELLM_FAILOVER_TIMEOUT", default_failover)
                child_env["LLM_TIMEOUT"] = os.environ.get("LLM_TIMEOUT", "60")
                proc = await asyncio.create_subprocess_exec(
                    *strategy_cmd,
                    cwd=str(PROJECT_ROOT),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=child_env,
                )
                async with self._lock:
                    self._active_procs.append(proc)

                out_task = asyncio.create_task(_pump_stream(proc.stdout, "stdout", label, local_lines))
                err_task = asyncio.create_task(_pump_stream(proc.stderr, "stderr", label, local_lines))
                await proc.wait()
                local_stdout = await out_task
                local_stderr = await err_task
                rc = int(proc.returncode or 0)

                lines = [ln.strip() for ln in local_lines if ln.strip()]
                timeout_hits = sum(
                    1
                    for ln in lines
                    if ("request timed out" in ln.lower())
                    or ("apitimeouterror" in ln.lower())
                    or ("[retry] llm timeout" in ln.lower())
                )
                for ln in reversed(lines):
                    m = re.search(r"\[done\]\s+summary=(.+)$", ln)
                    if m:
                        summary_path = m.group(1).strip()
                        break

                if not summary_path:
                    candidates = list(strategy_out_dir.glob("*/summary.json"))
                    if candidates:
                        latest = max(candidates, key=lambda p: p.stat().st_mtime)
                        summary_path = str(latest)

                if summary_path:
                    try:
                        payload = json.loads(Path(summary_path).read_text(encoding="utf-8"))
                        strategies = payload.get("strategies") or []
                        strategy_count = len(strategies)
                        improved_count = sum(
                            1 for s in strategies
                            if bool((s.get("best") or {}).get("improved_vs_baseline"))
                        )
                    except Exception:
                        improved_count = 0
                        strategy_count = 0
            finally:
                if proc is not None:
                    async with self._lock:
                        self._active_procs = [p for p in self._active_procs if p is not proc]

            return {
                "strategy": strategy_name,
                "return_code": rc,
                "summary_path": summary_path,
                "improved_count": improved_count,
                "strategy_count": strategy_count,
                "timeout_hits": timeout_hits,
                "stdout": local_stdout,
                "stderr": local_stderr,
            }

        try:
            tasks = [asyncio.create_task(_run_strategy(s)) for s in run_strategies]
            strategy_results = await asyncio.gather(*tasks, return_exceptions=True)
            chunks: List[str] = []
            for result in strategy_results:
                if isinstance(result, Exception):
                    return_code = 1
                    chunks.append(f"[error] worker exception: {result}")
                    continue
                rc = int(result.get("return_code", 1))
                if rc != 0:
                    return_code = 1
                sp = str(result.get("summary_path") or "").strip()
                if sp:
                    summary_paths.append(sp)
                improved_count_total += int(result.get("improved_count", 0))
                strategy_count_total += int(result.get("strategy_count", 0))
                timeout_hits_total += int(result.get("timeout_hits", 0))
                chunks.append(str(result.get("stdout") or ""))
                chunks.append(str(result.get("stderr") or ""))
            stdout_text = "\n".join([c for c in chunks if c]).strip()
            stderr_text = ""
        finally:
            async with self._lock:
                self._active_procs = []
                self.running = False
                self.last_finished_at = _utcnow()
                self.total_runs += 1
                # keep the UI-friendly normalized stream instead of raw stderr/stdout concat
                self.last_stdout_tail = "\n".join(all_lines[-120:])
                self.current_stdout_tail = ""
                self.last_summary_path = summary_paths[-1] if summary_paths else ""
                self.last_improved_count = int(improved_count_total)
                self.last_strategy_count = int(strategy_count_total)
                self.last_run_improved = bool(improved_count_total > 0 and strategy_count_total > 0)
                if timeout_hits_total > 0:
                    self._timeout_streak = min(8, self._timeout_streak + 1)
                else:
                    self._timeout_streak = 0
                success = return_code == 0
                self.last_success = success
                if success:
                    self.success_runs += 1
                    self.last_error = ""
                    if self.last_run_improved:
                        self.improved_runs += 1
                else:
                    self.failed_runs += 1
                    self.last_error = self.last_stdout_tail or f"return_code={return_code}"

        return {
            "success": return_code == 0,
            "return_code": return_code,
            "summary_path": summary_paths[-1] if summary_paths else "",
            "stdout_tail": self.last_stdout_tail,
        }


_SERVICE: Optional[LlmLoopAutomationService] = None


def get_llm_loop_automation_service() -> LlmLoopAutomationService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = LlmLoopAutomationService()
    return _SERVICE
