"""Unit tests for kernel.yaml_io — shared YAML serialize/atomic-write seam.

The kernel module is zero-dependency shared infrastructure used by
specify_cli, charter, and doctrine. These tests must remain independent of
all higher-level modules.

Coverage:
- serialize_mapping: trailing-whitespace normalization on wrapped scalars,
  safe-load round-trip equality, literal-scalar whitespace preservation,
  CommentedMap round-trip (pins the rt-dumper requirement — a safe dumper
  raises RepresenterError on a CommentedMap, which arbiter relies on).
- write_mapping_atomic: temp-then-rename atomicity, no trailing-whitespace
  lines in the written file.
- _normalize_nonsemantic_trailing_whitespace: YAMLError fallback returns the
  original bytes unchanged.

Red-first note: before src/kernel/yaml_io.py existed, every test in this file
failed at collection with ModuleNotFoundError: No module named 'kernel.yaml_io'.
That is the red-first evidence for this whole module — it was verified by
running this suite against the pre-migration tree (writer.py held the only
copy of the normalizer) before src/kernel/yaml_io.py was created.
"""

from __future__ import annotations

import os as _os
from pathlib import Path

import pytest
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import LiteralScalarString

from kernel.yaml_io import (
    CANONICAL_YAML_WIDTH,
    _normalize_nonsemantic_trailing_whitespace,
    serialize_mapping,
    write_mapping_atomic,
)

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# serialize_mapping
# ---------------------------------------------------------------------------


def test_serialize_mapping_strips_trailing_whitespace_from_wrapped_scalars() -> None:
    """A long prose scalar that wraps at a NARROW width leaves trailing
    whitespace on the wrap-continuation line; serialize_mapping must strip it,
    and the safe-load round-trip must still equal the original data.
    """
    details = (
        "An analysis-report.md artifact is present for this mission. Review "
        "its findings to understand documented issues and decisions that were "
        "made during implementation, then reconcile them against the record."
    )
    data = {
        "not_helpful": [
            {
                "id": "n-001",
                "category": "doc",
                "summary": "analysis-report.md present with findings",
                "evidence_refs": ["e-007"],
                "details": details,
            }
        ]
    }

    # Precondition guard: prove a dump at a narrow width genuinely wraps and
    # leaves a trailing-whitespace line, so this test cannot silently go
    # vacuous if a future ruamel stops emitting the artifact. Use width=80 to
    # force wrapping regardless of CANONICAL_YAML_WIDTH's own default.
    probe = YAML(typ="rt")
    probe.default_flow_style = False
    probe.preserve_quotes = True
    probe.width = 80
    from io import BytesIO

    probe_buf = BytesIO()
    probe.dump(data, probe_buf)
    raw = probe_buf.getvalue().decode("utf-8")
    assert any(line.endswith((" ", "\t")) for line in raw.splitlines()), (
        "expected the raw dump to contain a trailing-whitespace line; test is vacuous otherwise"
    )

    serialized = serialize_mapping(data, width=80)
    text = serialized.decode("utf-8")

    assert all(not line.endswith((" ", "\t")) for line in text.splitlines())
    assert YAML(typ="safe").load(text) == data


@pytest.mark.parametrize("trailing", [" ", "\t"])
def test_serialize_mapping_preserves_literal_scalar_trailing_whitespace(trailing: str) -> None:
    """A literal block scalar (``|``) may legitimately end a line in
    whitespace — that whitespace is semantically part of the content and
    must survive normalization untouched.
    """
    details = LiteralScalarString(f"first line ends in semantic whitespace{trailing}\nsecond line")

    serialized = serialize_mapping({"details": details})
    loaded = YAML(typ="safe").load(serialized.decode("utf-8"))

    assert loaded == {"details": str(details)}


def test_serialize_mapping_round_trips_commented_map_without_representer_error() -> None:
    """Pin the rt-dumper requirement: a CommentedMap loaded via a round-trip
    YAML instance must serialize through serialize_mapping with NO
    RepresenterError. This is exactly what arbiter's frontmatter-merge does
    (load existing frontmatter, mutate it, re-dump) — a safe (typ='safe')
    dumper raises RepresenterError on a CommentedMap, which is why
    serialize_mapping is contractually rt, not safe.
    """
    loader = YAML(typ="rt")
    loader.preserve_quotes = True
    source = "wp_id: WP07\nreviewer: reviewer-renata\nverdict: rejected\n"
    commented_map = loader.load(source)

    commented_map["arbiter_override"] = {"decided_by": "arbiter", "reason": "override"}

    # Must not raise RepresenterError.
    serialized = serialize_mapping(commented_map)

    loaded = YAML(typ="safe").load(serialized.decode("utf-8"))
    assert loaded["wp_id"] == "WP07"
    assert loaded["arbiter_override"] == {"decided_by": "arbiter", "reason": "override"}


def test_canonical_yaml_width_is_4096() -> None:
    assert CANONICAL_YAML_WIDTH == 4096


# ---------------------------------------------------------------------------
# write_mapping_atomic
# ---------------------------------------------------------------------------


def test_write_mapping_atomic_uses_temp_then_rename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The write must go through a .tmp sibling file and an os.replace rename
    — never a direct write to the target path.
    """
    target = tmp_path / "record.yaml"
    captured_replace: list[tuple[str, str]] = []
    original_replace = _os.replace

    def capturing_replace(src: str, dst: str) -> None:
        captured_replace.append((src, dst))
        original_replace(src, dst)

    monkeypatch.setattr(_os, "replace", capturing_replace)

    write_mapping_atomic({"x": 1}, target)

    assert len(captured_replace) == 1
    src_path, dst_path = captured_replace[0]
    assert Path(src_path).parent == target.parent
    assert ".tmp" in Path(src_path).name
    assert Path(dst_path) == target
    assert target.exists()
    assert not Path(src_path).exists()


def test_write_mapping_atomic_output_has_no_trailing_whitespace_lines(tmp_path: Path) -> None:
    target = tmp_path / "record.yaml"
    details = (
        "An analysis-report.md artifact is present for this mission. Review "
        "its findings to understand documented issues and decisions that were "
        "made during implementation, then reconcile them against the record."
    )
    write_mapping_atomic({"details": details}, target, width=80)

    text = target.read_text(encoding="utf-8")
    assert all(not line.endswith((" ", "\t")) for line in text.splitlines())
    assert YAML(typ="safe").load(text) == {"details": details}


def test_write_mapping_atomic_mkdir_creates_parent(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "dir" / "record.yaml"
    assert not target.parent.exists()

    write_mapping_atomic({"x": 1}, target, mkdir=True)

    assert target.exists()
    assert YAML(typ="safe").load(target.read_text(encoding="utf-8")) == {"x": 1}


def test_write_mapping_atomic_cleans_up_tempfile_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "record.yaml"

    def failing_write(fd: int, data: bytes) -> int:
        raise OSError("Simulated disk full")

    monkeypatch.setattr(_os, "write", failing_write)

    with pytest.raises(OSError):
        write_mapping_atomic({"x": 1}, target)

    assert not target.exists()
    leftover = [f for f in tmp_path.iterdir() if ".tmp" in f.name]
    assert leftover == [], f"Unexpected tempfiles left behind: {leftover}"


def test_write_mapping_atomic_crash_leaves_no_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "record.yaml"

    def crashing_replace(src: str, dst: str) -> None:
        raise OSError("Simulated crash mid-replace")

    monkeypatch.setattr(_os, "replace", crashing_replace)

    with pytest.raises(OSError):
        write_mapping_atomic({"x": 1}, target)

    assert not target.exists()


def test_write_mapping_atomic_dir_fsync_failure_is_non_fatal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Best-effort dir fsync failure does not propagate; the write still
    succeeds.
    """
    target = tmp_path / "record.yaml"
    original_fsync = _os.fsync
    fsync_call_count = [0]

    def flaky_fsync(fd: int) -> None:
        fsync_call_count[0] += 1
        # Fail only the second call (the directory fsync, after the file fsync).
        if fsync_call_count[0] >= 2:
            raise OSError("Simulated directory fsync failure")
        original_fsync(fd)

    monkeypatch.setattr(_os, "fsync", flaky_fsync)

    write_mapping_atomic({"x": 1}, target)

    assert target.exists()


# ---------------------------------------------------------------------------
# _normalize_nonsemantic_trailing_whitespace — YAMLError fallback
# ---------------------------------------------------------------------------


def test_normalize_yaml_error_fallback_returns_original_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the safety re-parse cannot confirm the normalized form is
    semantically identical (because it can't be parsed at all), the original
    (un-normalized) bytes must be returned unchanged.
    """
    from ruamel.yaml.error import YAMLError

    original = b"key: value \nother: thing\t\n"

    class ExplodingYAML:
        def __init__(self, typ: str = "safe") -> None:
            pass

        def load(self, stream: object) -> None:
            raise YAMLError("simulated unparsable input")

    import kernel.yaml_io as yaml_io_module

    monkeypatch.setattr(yaml_io_module, "YAML", ExplodingYAML)

    result = _normalize_nonsemantic_trailing_whitespace(original)
    assert result == original


def test_normalize_no_trailing_whitespace_is_a_noop() -> None:
    """When there is nothing to strip, the normalizer must return the exact
    same bytes object content without touching the YAML parser at all.
    """
    original = b"key: value\nother: thing\n"
    assert _normalize_nonsemantic_trailing_whitespace(original) == original
