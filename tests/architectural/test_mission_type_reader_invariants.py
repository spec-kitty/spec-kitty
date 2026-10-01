"""FR-010 structural invariants for the canonical mission-type reader (rc3 M5).

Two invariants pin the reader convergence as a *gate*, not 12 hand-copies:

* **Parity (AC-1).** Every in-scope reader that is expressible as a
  ``meta dict -> canonical key`` contract returns exactly what the one shared
  :func:`charter.mission_type_key.read_mission_type` returns for the same dict.
  The registry below is the enumeration; WP02/WP03 extend it as they converge
  additional readers.

* **No-legacy / no-default source-scan (AC-3, AC-7).** No in-scope reader module
  may carry a legacy ``mission``-field read (``.get("mission")`` /
  ``["mission"]``) or a ``"software-dev"`` mission-type fallback, except sites
  carried in the encoded, rationale-bearing allow-list
  (``tests/architectural/mission_type_reader_allowlist.yaml`` — distinct from the
  #883 ``inline_meta_read_allowlist.yaml`` FR-009 gate, which governs a different
  invariant (raw ``json.loads`` bypassing ``load_meta``);
  treated as empty until then). A newly-added reader that reintroduces either
  pattern trips this test (AC-7).

This test is authored RED: the source-scan fails against the not-yet-converged
readers (dashboard / mission_metadata / retrospective / context / verify /
diagnostics) and the write-boundary sites until WP02 converges the reads and
WP03 encodes the write-boundary exemptions.
"""

from __future__ import annotations

import ast
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = [pytest.mark.architectural]

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
ALLOWLIST_PATH = Path(__file__).resolve().parent / "mission_type_reader_allowlist.yaml"


# ---------------------------------------------------------------------------
# Part A — parity over the shared-authority reader registry (AC-1)
# ---------------------------------------------------------------------------

# Fixture matrix: every dict maps to a single expected canonical key (or None).
_META_MATRIX: list[dict[str, Any]] = [
    {"mission_type": "software-dev"},
    {"mission_type": "research"},
    {"mission_type": "  documentation  "},
    {},  # typeless
    {"mission_type": ""},  # blank
    {"mission_type": None},  # null
    {"mission_type": 123},  # non-string
    {"mission": "software-dev"},  # legacy-only — must NOT resolve
    {"mission_type": "research", "mission": "software-dev"},  # canonical wins
]


def _norm(value: str | None) -> str | None:
    """Normalize a reader's neutral result: ``""`` and ``None`` are equivalent."""
    return value or None


def _adapt_seam(meta: dict[str, Any]) -> str | None:
    from charter.activation.mission_type_key import read_mission_type

    return _norm(read_mission_type(meta))


def _adapt_cli_canonical(meta: dict[str, Any]) -> str | None:
    from specify_cli.mission import _canonical_meta_mission_type

    return _norm(_canonical_meta_mission_type(meta))


def _adapt_get_mission_type(meta: dict[str, Any], tmp_path: Path) -> str | None:
    """``specify_cli.mission.get_mission_type`` — file-based, ``""``-neutral."""
    from specify_cli.mission import get_mission_type

    feature_dir = tmp_path / "get_mission_type"
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return _norm(get_mission_type(feature_dir))


def _adapt_charter_resolve(meta: dict[str, Any], tmp_path: Path) -> str | None:
    """``charter.mission_type_profiles.resolve_mission_type_key`` — file-based."""
    from charter.activation.mission_type_profiles import resolve_mission_type_key

    feature_dir = tmp_path / "charter_resolve"
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return _norm(resolve_mission_type_key(feature_dir=feature_dir))


# Dict-in adapters (no filesystem).
_DICT_ADAPTERS: dict[str, Callable[[dict[str, Any]], str | None]] = {
    "charter.mission_type_key.read_mission_type": _adapt_seam,
    "specify_cli.mission._canonical_meta_mission_type": _adapt_cli_canonical,
}

# File-based adapters (need a tmp feature_dir).
_FILE_ADAPTERS: dict[str, Callable[[dict[str, Any], Path], str | None]] = {
    "specify_cli.mission.get_mission_type": _adapt_get_mission_type,
    "charter.mission_type_profiles.resolve_mission_type_key": _adapt_charter_resolve,
}


@pytest.mark.parametrize("meta", _META_MATRIX, ids=[str(m) for m in _META_MATRIX])
@pytest.mark.parametrize("name", sorted(_DICT_ADAPTERS))
def test_dict_reader_parity_with_shared_seam(name: str, meta: dict[str, Any]) -> None:
    reference = _adapt_seam(meta)
    assert _DICT_ADAPTERS[name](meta) == reference, f"{name} diverges from read_mission_type for {meta!r}"


@pytest.mark.parametrize("meta", _META_MATRIX, ids=[str(m) for m in _META_MATRIX])
@pytest.mark.parametrize("name", sorted(_FILE_ADAPTERS))
def test_file_reader_parity_with_shared_seam(name: str, meta: dict[str, Any], tmp_path: Path) -> None:
    reference = _adapt_seam(meta)
    assert _FILE_ADAPTERS[name](meta, tmp_path) == reference, f"{name} diverges from read_mission_type for {meta!r}"


# ---------------------------------------------------------------------------
# Part B — no-legacy / no-default source-scan (AC-3, AC-7)
# ---------------------------------------------------------------------------

# In-scope reader modules (repo-root-relative). Every module here must resolve
# the mission type through the shared seam: no legacy ``mission`` read, no
# ``"software-dev"`` fallback — unless carried in the allow-list.
IN_SCOPE_READER_MODULES: tuple[str, ...] = (
    "src/specify_cli/mission.py",
    "src/charter/activation/mission_type_profiles.py",
    "src/specify_cli/diagnostics/project.py",
    "src/specify_cli/mission_metadata.py",
    "src/specify_cli/retrospective/generator.py",
    "src/specify_cli/retrospective/reader.py",
    "src/specify_cli/retrospective/writer.py",
    "src/specify_cli/context/resolver.py",
    "src/specify_cli/verify_enhanced.py",
    "src/specify_cli/cli/commands/agent/mission_create.py",
    "src/specify_cli/upgrade/feature_meta.py",
    "src/specify_cli/doc_analysis/doc_state.py",
    "src/specify_cli/cli/commands/agent/mission_check_prerequisites.py",
)

_LEGACY_KEY = "mission"
_CANONICAL_KEY = "mission_type"
_DEFAULT_LITERAL = "software-dev"


def _load_allowlist() -> dict[str, set[str]]:
    """Return ``{module_path: {"legacy", "default"}}`` of encoded exemptions.

    Absent file → empty (WP01 authors this gate before WP03 creates the list).
    """
    if not ALLOWLIST_PATH.exists():
        return {}
    raw = yaml.safe_load(ALLOWLIST_PATH.read_text(encoding="utf-8")) or {}
    exemptions: dict[str, set[str]] = {}
    for entry in raw.get("exemptions", []):
        path = entry["path"]
        # Every exemption MUST carry an issue + rationale (no silent excludes).
        assert entry.get("issue"), f"allow-list entry for {path} missing 'issue'"
        assert entry.get("rationale"), f"allow-list entry for {path} missing 'rationale'"
        exemptions.setdefault(path, set()).update(entry.get("kinds", ["legacy", "default"]))
    return exemptions


def _is_legacy_const(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value == _LEGACY_KEY


def _legacy_mission_reads(tree: ast.AST) -> list[int]:
    """Line numbers where the retired legacy ``"mission"`` key is read.

    Catches three forms so a straight revert to the pre-M5 reader cannot slip
    past (the loop/field-tuple form IS the old ``_canonical_meta_mission_type``
    body — ``for field in ("mission_type", "mission"): meta.get(field)``):

    * ``x.get("mission")`` — direct call arg;
    * ``x["mission"]`` — subscript;
    * a ``("mission_type", "mission")`` field tuple/list — the reader
      loop-indirection form (``for field in (...): meta.get(field)``). Only a
      collection that carries BOTH the canonical and the legacy key is flagged, so
      an unrelated list that merely contains ``"mission"`` (e.g. a compat-ignore
      key set) is not a false positive.

    Known syntactic limit (defense-in-depth, not an open hole): a legacy key
    bound to an intermediate *variable* (``k = "mission"; meta.get(k)``) is not
    tracked — the Part-A parity registry is the semantic backstop for that.
    """
    hits: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get":
            hits.extend(arg.lineno for arg in node.args if _is_legacy_const(arg))
        elif isinstance(node, ast.Subscript) and _is_legacy_const(node.slice):
            hits.append(node.lineno)
        elif isinstance(node, (ast.Tuple, ast.List)):
            values = {elt.value for elt in node.elts if isinstance(elt, ast.Constant)}
            if _LEGACY_KEY in values and _CANONICAL_KEY in values:
                hits.extend(elt.lineno for elt in node.elts if _is_legacy_const(elt))
    return sorted(set(hits))


def _software_dev_literals(tree: ast.AST) -> list[int]:
    """Line numbers of ``"software-dev"`` string constants (fallback candidates)."""
    return [node.lineno for node in ast.walk(tree) if isinstance(node, ast.Constant) and node.value == _DEFAULT_LITERAL]


@pytest.mark.parametrize(
    ("snippet", "should_flag"),
    [
        ('y = meta.get("mission")', True),  # direct call
        ('y = meta["mission"]', True),  # subscript
        ('for f in ("mission_type", "mission"):\n    y = meta.get(f)', True),  # loop-revert
        ('IGNORED = ("mission", "initial", "states")', False),  # innocent list — no false positive
        ('y = meta.get("mission_type")', False),  # canonical read
    ],
)
def test_scan_detector_catches_reverts_without_false_positives(snippet: str, should_flag: bool) -> None:
    """Pin the Part-B detector's own reach (defense-in-depth against a weakened gate).

    A straight revert to the pre-M5 reader — direct, subscript, or the
    ``("mission_type", "mission")`` loop form — must be caught; an unrelated list
    that merely mentions ``"mission"`` must not.
    """
    assert bool(_legacy_mission_reads(ast.parse(snippet))) is should_flag


@pytest.mark.parametrize("module_path", IN_SCOPE_READER_MODULES)
def test_no_legacy_read_or_software_dev_fallback(module_path: str) -> None:
    allowlist = _load_allowlist()
    allowed = allowlist.get(module_path, set())
    tree = ast.parse((REPO_ROOT / module_path).read_text(encoding="utf-8"))

    legacy = _legacy_mission_reads(tree)
    if legacy and "legacy" not in allowed:
        pytest.fail(
            f"{module_path} reads the retired legacy 'mission' field at line(s) {legacy} "
            f"(FR-002). Route through read_mission_type, or add an encoded allow-list exemption."
        )

    default = _software_dev_literals(tree)
    if default and "default" not in allowed:
        pytest.fail(
            f"{module_path} carries a 'software-dev' literal at line(s) {default} (FR-003). Remove the silent default, or add an encoded allow-list exemption."
        )
