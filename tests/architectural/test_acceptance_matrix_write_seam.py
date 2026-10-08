"""Architectural ratchet: acceptance-matrix write-seam call sites in ``src/``.

``write_acceptance_matrix`` and ``write_and_commit_acceptance_matrix``
(``src/specify_cli/acceptance/matrix.py``) are the ONLY raw writers of
``acceptance-matrix.json``; every other production module MUST route through
the ONE locked read-modify-write critical section,
:func:`~specify_cli.acceptance.matrix.locked_reread_splice_and_write`
(#4887), rather than growing a second, unlocked writer that could
reintroduce the lost-update class #4887 named as the root cause of #4974.

The scan is AST-based and catches the three direct call shapes a production
module could use to reach the raw writers (indirect references such as
``getattr`` lookups or passing the function as a callback are out of reach,
and are a review concern):

1. **Name form** -- ``write_acceptance_matrix(...)`` after
   ``from specify_cli.acceptance.matrix import write_acceptance_matrix``.
2. **Attribute form** -- ``matrix.write_acceptance_matrix(...)`` via a
   module-qualified import.
3. **Aliased-import form** -- ``from ...matrix import write_acceptance_matrix
   as w`` followed by ``w(...)``.

Each caller is keyed by ``path::qualname`` -- the file's repo-relative path
and the OUTERMOST enclosing named function a call lives in (nested closures
attribute to their enclosing named function, since a raw write hidden inside
a closure is exactly as much a blind-writer risk as one at the top level of
that function). This is a shrink-only allowlist: a stale entry --
one the live scan no longer finds -- fails, so removing a caller must also
tighten this file.

Every allowed caller carries a one-line rationale (below); anything the scan
finds outside this allowlist is a FINDING TO REPORT, never something to
silently allowlist.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_ROOT = _REPO_ROOT / "src"

#: The raw writers this ratchet guards. Both live in the seam's own home
#: module; neither name is used anywhere else in the codebase, so matching
#: on the bare name (Name/Attribute) is unambiguous without also checking
#: import provenance.
_WRITE_SEAM_TARGETS = frozenset({"write_acceptance_matrix", "write_and_commit_acceptance_matrix"})

#: ``path::qualname`` -> one-line rationale. Shrink-only: a key the
#: live scan no longer finds fails ``test_write_seam_allowlist_has_no_stale_entries``.
_ALLOWED_WRITE_SEAM_CALLERS: dict[str, str] = {
    # The ONE locked read-modify-write critical section itself (#4887)
    # -- every acceptance-matrix writer is meant to route through THIS, so it
    # is the seam's own home, not a caller to police.
    "src/specify_cli/acceptance/matrix.py::locked_reread_splice_and_write": (
        "the seam itself -- routes commit=True through write_and_commit_acceptance_matrix "
        "and commit=False through the raw write_acceptance_matrix, under the shared "
        "per-mission status lock"
    ),
    # The commit-aware wrapper around the raw writer. It composes the raw
    # write with the shared write-seam's commit routing; both the locked seam
    # above and scaffold_acceptance_matrix below call it as their "commit"
    # leg, so it is a wrapper, not an independent blind writer.
    "src/specify_cli/acceptance/matrix.py::write_and_commit_acceptance_matrix": (
        "wraps the raw writer inside the shared write-seam's stage= thunk -- the one sanctioned commit-and-write composition"
    ),
    # Idempotent create-if-absent at task-finalization time -- never
    # overwrites an existing matrix, so it cannot race a real accept/verdict
    # writer over the SAME row content (D6 / research.md).
    "src/specify_cli/acceptance/matrix.py::_scaffold_acceptance_matrix_locked": "create-if-absent at finalize (idempotent scaffold; D6), one lock hold",
    # No production caller today -- post-consolidation seam routing through
    # the locked seam is explicitly deferred (research.md D6); this
    # is a known, allowlisted blind creator, not an oversight.
    "src/specify_cli/acceptance/post_consolidation.py::verify_deferred_invariants": ("no production caller; post-consolidation seam routing deferred"),
}

#: Production callers of ``record_acceptance`` (``mission_metadata.py``) are
#: pinned to exactly one site: ``acceptance/__init__.py``'s
#: pre-stamp-guard helper. Host ``accept`` and orchestrator ``accept-mission``
#: both stamp through it, so a second direct caller would be an unguarded
#: stamp path.
_ALLOWED_RECORD_ACCEPTANCE_CALLERS: dict[str, str] = {
    "src/specify_cli/acceptance/__init__.py::_stamp_acceptance_record": (
        "the pre-stamp-guard helper -- records acceptance inside "
        "locked_acceptance_verdict_guard (and, for the one legitimate "
        "planning-artifact-only bypass, without it)"
    ),
}


def _iter_src_python_files(repo_root: Path = _REPO_ROOT) -> list[Path]:
    return sorted(p for p in (repo_root / "src").rglob("*.py") if "__pycache__" not in p.parts)


def _rel(path: Path, repo_root: Path = _REPO_ROOT) -> str:
    return path.relative_to(repo_root).as_posix()


class _WriteSeamCallVisitor(ast.NodeVisitor):
    """Walks one module, attributing each matched call to its OUTERMOST
    enclosing named function (``"<module>"`` for module-level calls)."""

    def __init__(self, target_names: frozenset[str]) -> None:
        self._target_names = target_names
        self._class_stack: list[str] = []
        self._function_stack: list[str] = []
        #: local-name -> canonical target name, for aliased ``from ... import
        #: X as Y`` bindings.
        self._alias_map: dict[str, str] = {}
        self.found: list[tuple[str, str]] = []

    def _owner(self) -> str:
        if self._class_stack and self._function_stack:
            return f"{self._class_stack[-1]}.{self._function_stack[-1]}"
        if self._function_stack:
            return self._function_stack[-1]
        return "<module>"

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name in self._target_names and alias.asname:
                self._alias_map[alias.asname] = alias.name
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        # Only the OUTERMOST named function pushes a new owner frame -- a
        # nested closure's calls attribute to the function that defines it,
        # since a raw write hidden inside a closure is the same blind-writer
        # risk as one at that function's top level.
        pushed = not self._function_stack
        if pushed:
            self._function_stack.append(node.name)
        self.generic_visit(node)
        if pushed:
            self._function_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _resolve_target(self, func: ast.expr) -> str | None:
        if isinstance(func, ast.Name):
            if func.id in self._target_names:
                return func.id
            return self._alias_map.get(func.id)
        if isinstance(func, ast.Attribute) and func.attr in self._target_names:
            return func.attr
        return None

    def visit_Call(self, node: ast.Call) -> None:
        target = self._resolve_target(node.func)
        if target is not None:
            self.found.append((self._owner(), target))
        self.generic_visit(node)


def _census(target_names: frozenset[str], repo_root: Path = _REPO_ROOT) -> dict[str, set[str]]:
    """Map ``"path::qualname"`` -> the set of ``target_names`` called there."""
    census: dict[str, set[str]] = {}
    for path in _iter_src_python_files(repo_root):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        visitor = _WriteSeamCallVisitor(target_names)
        visitor.visit(tree)
        rel = _rel(path, repo_root)
        for owner, target in visitor.found:
            key = f"{rel}::{owner}"
            census.setdefault(key, set()).add(target)
    return census


def test_write_seam_census_has_concrete_floor() -> None:
    """Non-vacuity: the scan actually finds the seam's own calls,
    so a broken/no-op scan can never silently pass this ratchet."""
    census = _census(_WRITE_SEAM_TARGETS)
    seam_key = "src/specify_cli/acceptance/matrix.py::locked_reread_splice_and_write"
    assert seam_key in census, (
        f"Concrete floor: the AST scan found no calls in {seam_key} at all -- "
        "the scan itself is broken (it should find the seam's own calls to "
        "write_and_commit_acceptance_matrix / write_acceptance_matrix)."
    )
    assert census[seam_key] == _WRITE_SEAM_TARGETS


def test_write_seam_callers_are_allowlisted() -> None:
    """Every production caller of the raw acceptance-matrix writers is one of
    the allowlisted, individually-justified call sites above."""
    census = _census(_WRITE_SEAM_TARGETS)
    unexpected = set(census) - set(_ALLOWED_WRITE_SEAM_CALLERS)
    assert not unexpected, (
        f"Unallowlisted caller(s) of the raw acceptance-matrix writer(s): {sorted(unexpected)}. "
        "Every write to acceptance-matrix.json must route through "
        "locked_reread_splice_and_write (#4887) unless it is one of the "
        "individually-justified exceptions above -- this is a finding to "
        "report, not to silently allowlist."
    )


def test_write_seam_allowlist_has_no_stale_entries() -> None:
    """Shrink-only: every allowlisted key must still be a real call
    site, or the allowlist has drifted from the code it describes."""
    census = _census(_WRITE_SEAM_TARGETS)
    stale = set(_ALLOWED_WRITE_SEAM_CALLERS) - set(census)
    assert not stale, f"Stale allowlist entries (no longer call the write seam): {sorted(stale)}. Remove them."


def test_record_acceptance_callers_are_exactly_the_guarded_sites() -> None:
    """The only production caller of ``record_acceptance`` is the
    guarded stamping helper named above -- no second, unguarded call site."""
    census = _census(frozenset({"record_acceptance"}))
    actual = set(census)
    expected = set(_ALLOWED_RECORD_ACCEPTANCE_CALLERS)
    assert actual == expected, (
        f"record_acceptance callers drifted from the expected guarded-site set.\n"
        f"  unexpected (found, not allowlisted): {sorted(actual - expected)}\n"
        f"  missing (allowlisted, but no longer found): {sorted(expected - actual)}"
    )


def test_write_seam_scan_catches_aliased_and_attribute_calls(tmp_path: Path) -> None:
    """Self-mutation: plants an aliased-import call AND an
    attribute-form call in a throwaway ``src/`` tree and asserts the scan
    catches both -- proving the AST scan cannot be defeated by either shape."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    aliased_probe = src_dir / "aliased_probe.py"
    aliased_probe.write_text(
        "from specify_cli.acceptance.matrix import write_acceptance_matrix as _sneaky_write\n"
        "\n"
        "\n"
        "def do_the_write(feature_dir, matrix):\n"
        "    return _sneaky_write(feature_dir, matrix)\n",
        encoding="utf-8",
    )

    attribute_probe = src_dir / "attribute_probe.py"
    attribute_probe.write_text(
        "from specify_cli.acceptance import matrix as matrix_module\n"
        "\n"
        "\n"
        "def do_the_other_write(feature_dir, m):\n"
        "    return matrix_module.write_and_commit_acceptance_matrix(feature_dir, m)\n",
        encoding="utf-8",
    )

    census = _census(_WRITE_SEAM_TARGETS, repo_root=tmp_path)

    assert census.get("src/aliased_probe.py::do_the_write") == {"write_acceptance_matrix"}, (
        "the scan must catch an aliased-import call (`from ... import X as w`, then `w(...)`)"
    )
    assert census.get("src/attribute_probe.py::do_the_other_write") == {"write_and_commit_acceptance_matrix"}, (
        "the scan must catch an attribute-form call (`module.write_and_commit_acceptance_matrix(...)`)"
    )
