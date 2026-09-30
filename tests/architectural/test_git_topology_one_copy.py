"""One-copy static gates for the unified git-topology primitive (WP01, #3373).

Mission ``write-path-integrity-01KZZD69`` collapsed four re-implementations of
the git-common-dir / toplevel probe into one primitive, the ~12x
owned/default meta-read fork into one ``read_dir_for`` helper, and the
nested/toplevel-mismatch classifier into that single primitive. These gates make
the consolidation hard to silently undo:

* SC-005 — exactly one ``git_common_dir`` / ``git_toplevel`` primitive, and none
  of the four migrated call sites still shells out to ``rev-parse`` for topology.
* SC-007 — exactly one ``read_dir_for``, and the ``compose_meta_json_path`` meta
  fork it once owned is gone from the resolver module (the owned arm reads the fact).
* SC-008 — the toplevel-mismatch classifier (``--show-toplevel``) has one
  authority: the primitive. The two classifier consumers carry no raw probe.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"

_PRIMITIVE = _SRC / "kernel" / "git_topology.py"
_RESOLUTION = _SRC / "mission_runtime" / "resolution.py"

# The four probe sites migrated onto the primitive (WP01 T002/T003/T005).
_MIGRATED_CONSUMERS = (
    _SRC / "charter" / "resolution.py",
    _SRC / "specify_cli" / "core" / "checkout_ownership.py",
    _SRC / "specify_cli" / "git" / "commit_helpers.py",
    _SRC / "specify_cli" / "workspace" / "context.py",
)

_COMMON_DIR_FLAG = '"--git-common-dir"'
_TOPLEVEL_FLAG = '"--show-toplevel"'


def _count_function_defs(module: Path, name: str) -> list[Path]:
    """Return the file(s) defining a top-level function ``name`` under ``src/``."""
    hits: list[Path] = []
    for py in module.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        if any(
            isinstance(node, ast.FunctionDef) and node.name == name
            for node in ast.walk(tree)
        ):
            hits.append(py)
    return hits


def _count_calls(path: Path, callee: str) -> int:
    """Count call expressions whose (possibly attribute) callee ends in ``callee``."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    total = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        target = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if target == callee:
            total += 1
    return total


# ---------------------------------------------------------------------------
# SC-005 — one primitive; the four call sites consume it
# ---------------------------------------------------------------------------


def test_exactly_one_git_common_dir_primitive() -> None:
    defs = _count_function_defs(_SRC, "git_common_dir")
    assert defs == [_PRIMITIVE], (
        f"Expected exactly one git_common_dir definition (the primitive); found {defs}."
    )


def test_exactly_one_git_toplevel_primitive() -> None:
    defs = _count_function_defs(_SRC, "git_toplevel")
    assert defs == [_PRIMITIVE], (
        f"Expected exactly one git_toplevel definition (the primitive); found {defs}."
    )


def test_migrated_call_sites_carry_no_raw_topology_probe() -> None:
    for consumer in _MIGRATED_CONSUMERS:
        text = consumer.read_text(encoding="utf-8")
        assert _COMMON_DIR_FLAG not in text, (
            f"{consumer} still shells out to `rev-parse --git-common-dir`; it must "
            "consume the git_topology primitive instead (WP01 #3373)."
        )
        assert _TOPLEVEL_FLAG not in text, (
            f"{consumer} still shells out to `rev-parse --show-toplevel`; it must "
            "consume the git_topology primitive instead (WP01 #3373)."
        )


def test_primitive_owns_both_probe_flags() -> None:
    text = _PRIMITIVE.read_text(encoding="utf-8")
    assert _COMMON_DIR_FLAG in text and _TOPLEVEL_FLAG in text, (
        "The git_topology primitive must be the single owner of the "
        "--git-common-dir / --show-toplevel probe flags."
    )


# ---------------------------------------------------------------------------
# SC-007 — one read_dir_for; one meta-read fork
# ---------------------------------------------------------------------------


def test_exactly_one_read_dir_for() -> None:
    defs = _count_function_defs(_SRC, "read_dir_for")
    assert defs == [_RESOLUTION], (
        f"Expected exactly one read_dir_for definition (the fork authority); found {defs}."
    )


def test_meta_read_fork_compose_call_is_single_copy() -> None:
    # WP18 retired the ``effective_root`` fork: the owned arm of ``read_dir_for``
    # reads ``owned.mission_dir`` directly, so the ``compose_meta_json_path``
    # meta-read compose must not reappear anywhere in the resolver module (zero
    # copies -- a re-inlined fork would be a second, uncounted authority).
    assert _count_calls(_RESOLUTION, "compose_meta_json_path") == 0, (
        "compose_meta_json_path must not be called in resolution.py "
        "(the owned arm of read_dir_for reads owned.mission_dir); a call means the "
        "retired effective_root meta fork was re-inlined (WP01 #3373 SC-007, WP18)."
    )


# ---------------------------------------------------------------------------
# SC-008 — one nested/toplevel-mismatch classifier
# ---------------------------------------------------------------------------


def test_nested_classifier_has_single_toplevel_authority() -> None:
    # The two classifier consumers (linkage fast gate + ownership comparator)
    # must route their toplevel-mismatch check through the primitive, not a raw
    # --show-toplevel probe.
    classifier_consumers = (
        _SRC / "specify_cli" / "git" / "commit_helpers.py",
        _SRC / "specify_cli" / "core" / "checkout_ownership.py",
    )
    for consumer in classifier_consumers:
        assert _TOPLEVEL_FLAG not in consumer.read_text(encoding="utf-8"), (
            f"{consumer} must classify nested/toplevel mismatch via the "
            "git_topology primitive, not a raw --show-toplevel probe (WP01 SC-008)."
        )
