"""NFR-002 (#5697): an unclassified artifact kind has ONE meaning, via ONE authority.

``kind_for_mission_file -> None`` means "not a coordination record". The two consumers
that used to read it as "coordination bookkeeping" must decide through the canonical
mission-runtime classification — either the ``coordination.coherence.is_coordination_kind_file``
wrapper, or the exact pair it wraps (``mission_runtime.kind_for_mission_file`` +
``mission_runtime.is_primary_artifact_kind``) — and must never contain a positive
``is None`` / ``== None`` branch that routes the unclassified case into a
coord/projected bucket.

(``_post_checkpoint_mission_paths`` uses the wrapper; ``_partition_paths_by_primary_kind``
lives in a trio-seam module that may not import the ``KITTY_SPECS_DIR`` primitive the
wrapper's tail needs — ``test_trio_seam_only.py`` — so it decides through the pair the
wrapper is built from. Both are the same single authority.)
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architectural]

_SRC = Path(__file__).resolve().parents[2] / "src" / "specify_cli"
_WRAPPER = "is_coordination_kind_file"
#: The pair the wrapper is built from; referencing BOTH is equivalent to the wrapper.
_CLASSIFIER_PAIR = ("kind_for_mission_file", "is_primary_artifact_kind")
_FLOOR: dict[str, tuple[str, str]] = {
    "projection": ("consolidation/bookkeeping_projection.py", "_post_checkpoint_mission_paths"),
    "partition": ("cli/commands/agent/workflow.py", "_partition_paths_by_primary_kind"),
}
_BUCKET_HINTS = ("coord", "project", "paths")


def _function(relpath: str, name: str) -> ast.FunctionDef:
    tree = ast.parse((_SRC / relpath).read_text(encoding="utf-8"))
    found = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name]
    assert len(found) == 1, f"{relpath}: expected exactly one {name}, found {len(found)}"
    return found[0]


def _names(fn: ast.FunctionDef) -> set[str]:
    return {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}


def _references_authority(fn: ast.FunctionDef) -> bool:
    """True iff the verdict comes from the canonical classifier (wrapper OR its pair)."""
    names = _names(fn)
    return _WRAPPER in names or all(member in names for member in _CLASSIFIER_PAIR)


def _is_positive_none_compare(test: ast.expr) -> bool:
    """A POSITIVE unclassified match: ``<x> is None`` / ``<x> == None`` (not ``is not``).

    This is the pre-#5697 regression shape — the None case is the matched (true)
    branch. ``is not None`` / ``!= None`` (the None case falls through to ``else``)
    is deliberately NOT flagged, so ``if kind is not None and not primary: coord``
    (None -> primary) is allowed.
    """
    return any(
        isinstance(n, ast.Compare)
        and any(isinstance(op, (ast.Is, ast.Eq)) for op in n.ops)
        and any(isinstance(c, ast.Constant) and c.value is None for c in [n.left, *n.comparators])
        for n in ast.walk(test)
    )


def _appends_to_bucket(body: list[ast.stmt]) -> bool:
    for stmt in body:
        for n in ast.walk(stmt):
            if (
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and n.func.attr == "append"
                and isinstance(n.func.value, ast.Name)
                and any(h in n.func.value.id for h in _BUCKET_HINTS)
            ):
                return True
    return False


def _none_branches_into_bucket(fn: ast.FunctionDef) -> list[int]:
    return [n.lineno for n in ast.walk(fn) if isinstance(n, ast.If) and _is_positive_none_compare(n.test) and _appends_to_bucket(n.body)]


def test_floor_set_is_exactly_the_two_none_consumers() -> None:
    assert set(_FLOOR) == {"projection", "partition"}
    for relpath, name in _FLOOR.values():
        assert _function(relpath, name).name == name


@pytest.mark.parametrize("key", sorted(_FLOOR))
def test_consumer_decides_through_the_single_authority(key: str) -> None:
    relpath, name = _FLOOR[key]
    fn = _function(relpath, name)

    assert _references_authority(fn), f"{name} must decide via {_WRAPPER} or the {_CLASSIFIER_PAIR} pair"
    assert _none_branches_into_bucket(fn) == [], f"{name} must not branch on `is None` into a coord bucket"


def test_detector_is_not_vacuous() -> None:
    """The scan flags the pre-#5697 shape and accepts BOTH fixed forms."""
    bad = ast.parse(
        "def f(paths):\n    coord_bound = []\n    for p in paths:\n        kind = classify(p)\n        if kind is None:\n            coord_bound.append(p)\n"
    ).body[0]
    good_wrapper = ast.parse("def f(paths):\n    out = []\n    for p in paths:\n        if is_coordination_kind_file(p):\n            out.append(p)\n").body[0]
    good_pair = ast.parse(
        "def f(paths):\n"
        "    coord = []\n"
        "    for p in paths:\n"
        "        kind = kind_for_mission_file(p)\n"
        "        if kind is not None and not is_primary_artifact_kind(kind):\n"
        "            coord.append(p)\n"
    ).body[0]
    assert isinstance(bad, ast.FunctionDef) and isinstance(good_wrapper, ast.FunctionDef) and isinstance(good_pair, ast.FunctionDef)
    # Pre-#5697 regression shape: flagged, and uses no canonical authority.
    assert _none_branches_into_bucket(bad) != []
    assert not _references_authority(bad)
    # Wrapper form: clean, references the authority.
    assert _none_branches_into_bucket(good_wrapper) == []
    assert _references_authority(good_wrapper)
    # Pair form (trio-seam-safe): the `is not None` coord branch is NOT a regression,
    # and the pair counts as the authority.
    assert _none_branches_into_bucket(good_pair) == []
    assert _references_authority(good_pair)
