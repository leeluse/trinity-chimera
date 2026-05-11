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
