import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from server.modules.chat.skills.pipeline_modify import (
    _compute_line_patches,
    _validate_line_patches,
)


def test_replace_single_block():
    before = "a = 1\nb = 2\nc = 3\n"
    after  = "a = 1\nb = 99\nc = 3\n"
    patches = _compute_line_patches(before, after)
    assert len(patches) == 1
    p = patches[0]
    assert p["start_line"] == 2
    assert p["end_line"]   == 2
    assert p["new_content"] == "b = 99"


def test_delete_lines():
    before = "a\nb\nc\nd\n"
    after  = "a\nd\n"
    patches = _compute_line_patches(before, after)
    assert len(patches) == 1
    p = patches[0]
    assert p["start_line"] == 2
    assert p["end_line"]   == 3
    assert p["new_content"] == ""


def test_insert_lines():
    before = "a\nc\n"
    after  = "a\nb\nc\n"
    patches = _compute_line_patches(before, after)
    assert len(patches) == 1
    p = patches[0]
    # 삽입: end_line = start_line - 1 (삭제 0줄)
    assert p["start_line"] == p["end_line"] + 1
    assert p["start_line"] == 2
    assert p["end_line"] == 1
    assert p["new_content"] == "b"


def test_no_change():
    code = "a = 1\nb = 2\n"
    patches = _compute_line_patches(code, code)
    assert patches == []


def test_validate_ok():
    before = "a\nb\nc\n"
    patches = [{"start_line": 2, "end_line": 2, "new_content": "x"}]
    assert _validate_line_patches(patches, before) is None


def test_validate_out_of_range():
    before = "a\nb\n"
    patches = [{"start_line": 1, "end_line": 5, "new_content": "x"}]
    err = _validate_line_patches(patches, before)
    assert err is not None


def test_validate_bad_order():
    before = "a\nb\nc\n"
    patches = [{"start_line": 3, "end_line": 1, "new_content": "x"}]
    err = _validate_line_patches(patches, before)
    assert err is not None


import asyncio

def test_patch_event_emitted():
    """patch_first 성공 시 patch 이벤트가 전송되는지 확인."""
    import json
    from unittest.mock import AsyncMock, patch as mock_patch

    before_code = (
        "import numpy as np\n"
        "import pandas as pd\n"
        "\n"
        "def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:\n"
        "    sig = pd.Series(0, index=test_df.index)\n"
        "    return sig.fillna(0).astype(int)\n"
    )
    after_code = (
        "import numpy as np\n"
        "import pandas as pd\n"
        "\n"
        "def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:\n"
        "    sig = pd.Series(1, index=test_df.index)\n"
        "    return sig.fillna(0).astype(int)\n"
    )

    patch_result = {
        "ok": True,
        "code": after_code,
        "title": "Test Strategy",
        "summary": "Changed 0 to 1",
        "applied": 1,
        "requested": 1,
        "ratio": 0.1,
    }

    async def fake_backtest(*args, **kwargs):
        return
        yield  # make it an async generator

    events = []

    async def run():
        from server.modules.chat.skills.pipeline_modify import run_modify_pipeline
        db_mock = AsyncMock()
        db_mock.save_chat_message = AsyncMock()
        sm = {}
        context = {"editor_code": before_code}

        db_mock.get_last_strategy_message = AsyncMock(return_value=None)
        db_mock.get_last_strategy_message_any = AsyncMock(return_value=None)
        db_mock.get_last_strategy_row = AsyncMock(return_value=None)

        with mock_patch(
            "server.modules.chat.skills.pipeline_modify._attempt_patch_first",
            new=AsyncMock(return_value=patch_result),
        ), mock_patch(
            "server.modules.chat.skills.pipeline_modify.run_backtest",
            return_value=fake_backtest(),
        ), mock_patch(
            "server.modules.chat.skills.pipeline_modify.EvolutionWikiMemory",
        ):
            async for raw in run_modify_pipeline("RSI 추가", "s1", context, [], db_mock, sm):
                try:
                    obj = json.loads(raw.replace("data: ", "").strip())
                    events.append(obj)
                except Exception:
                    pass

    asyncio.run(run())
    types = [e.get("type") for e in events]
    assert "patch" in types, f"patch 이벤트 없음, got: {types}"
    patch_event = next(e for e in events if e.get("type") == "patch")
    assert "patches" in patch_event.get("data", {}), "patches 키 없음"
    assert len(patch_event["data"]["patches"]) > 0, "patches 목록이 비어 있음"
