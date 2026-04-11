from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MAX_CHARS = 6000


def _resolve_skill_md_path() -> Path | None:
    candidates = [
        PROJECT_ROOT / "server" / "backtesting-trading-strategies" / "SKILL.md",
        PROJECT_ROOT / ".agents" / "skills" / "backtesting-trading-strategies" / "SKILL.md",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    return text[end + 4 :].lstrip()


@lru_cache(maxsize=1)
def get_backtesting_skill_system_appendix() -> str:
    """
    Returns a compact SKILL.md excerpt for LLM system prompt injection.
    Cached in-process to avoid re-reading file on every request.
    """
    path = _resolve_skill_md_path()
    if path is None:
        return ""

    try:
        max_chars = int(os.getenv("BACKTEST_SKILL_PROMPT_MAX_CHARS", str(DEFAULT_MAX_CHARS)))
    except ValueError:
        max_chars = DEFAULT_MAX_CHARS
    max_chars = max(1000, min(max_chars, 20000))

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return ""

    body = _strip_frontmatter(raw).strip()
    if not body:
        return ""

    excerpt = body[:max_chars]
    return (
        "백테스트 스킬 가이드(SKILL.md) 발췌를 참고해서 답변하라. "
        "코드/전략 설명은 아래 가이드와 일관되게 유지하라.\n\n"
        f"{excerpt}"
    )

