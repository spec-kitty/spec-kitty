"""Architectural gate: FR-010's ledger floor.

The ledger flag (``ledger.projection``) may only ever gate the *derived*,
gitignored execution-state projection (``status/views.py::refresh_execution_
projection`` and its ``.kittify/derived/<slug>/`` output). It must never be
reachable from -- or influence -- the surfaces that are the non-optional
floor no flag in this mission may touch (spec.md Invariant / #4311, "Git
carries DONE"):

* the lane ledger itself (``status/store.py``, ``status/reducer.py``)
* the coordination-transaction commit machinery (``coordination/
  transaction.py``)
* the decision ledger (``src/specify_cli/decisions/**``,
  ``src/specify_cli/events/decision_log.py``)

This gate keys on the REFERENCE (an AST scan for any use of
``hosted_posture.ledger_posture`` / ``hosted_posture.drain_posture`` --
attribute access (through the canonical module name OR an ``import ... as``/
``from ... import hosted_posture as`` alias of the module itself), a bare
imported name, or an import statement), not a literal string ``grep``, which
a rename or an indirection could dodge -- modelled on
``tests/architectural/test_egress_consent_boundary.py``'s sink-reference-scan
rationale.

Two axes:

1. **Forbidden files** (:data:`_FORBIDDEN_FILES` / :data:`_FORBIDDEN_DIRS`)
   -- ``ledger_posture``/``drain_posture`` must be referenced ZERO times
   anywhere in these files. :func:`_assert_no_forbidden_reference` is the one
   assertion helper both the real test and its self-mutation check run.
2. **``coordination/status_transition.py`` allow-list** -- ``ledger_posture``
   may be referenced ONLY inside the enumerated hook-site functions
   (:data:`_ALLOWED_STATUS_TRANSITION_FUNCTIONS`, T024), and EVERY one of
   those functions must reference it (set equality, not "no offenders",
   review cycle 1 / B3.1) -- :func:`_assert_ledger_posture_allowlist` is the
   one assertion helper both the real test and its self-mutation check run.

:class:`TestGuardBites` proves both scanners are non-vacuous by running the
SAME assertion helpers the real tests run, against synthetic/mutated source
that is missing a permitted hook site or carries a planted (possibly
aliased) forbidden reference, and asserting they raise.
"""

from __future__ import annotations

import ast
import textwrap
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_ROOT = _REPO_ROOT / "src"

_HOSTED_POSTURE_NAMES = frozenset({"ledger_posture", "drain_posture"})
_HOSTED_POSTURE_MODULE_TAIL = "hosted_posture"

# Files that must carry ZERO references to ledger_posture/drain_posture.
_FORBIDDEN_FILES: tuple[str, ...] = (
    "specify_cli/status/store.py",
    "specify_cli/status/reducer.py",
    "specify_cli/coordination/transaction.py",
    "specify_cli/events/decision_log.py",
)
# Directories that must carry ZERO references (walked recursively).
_FORBIDDEN_DIRS: tuple[str, ...] = ("specify_cli/decisions",)

# The only functions in coordination/status_transition.py allowed to
# reference ledger_posture (T024 hook sites). Re-grepped against live code
# at WP05 authoring time:
#   * `_fan_out_committed_coord_tail` -- the non-transactional coord-tail
#     fan-out (the direct `_emit._saas_fan_out` call site).
#   * `_defer_fan_out` -- the shared choke point for both the single-door
#     (`emit_status_transition_transactional`) and batch-door
#     (`emit_status_transition_batch_transactional`) transactional paths.
#   * `emit_inner_state_changed_transactional` -- the inner-state annotation
#     door (persists an `InnerStateChanged` annotation, not a lane-transition
#     `StatusEvent`).
_ALLOWED_STATUS_TRANSITION_FUNCTIONS: frozenset[str] = frozenset(
    {
        "_fan_out_committed_coord_tail",
        "_defer_fan_out",
        "emit_inner_state_changed_transactional",
    }
)

_STATUS_TRANSITION_RELPATH = "specify_cli/coordination/status_transition.py"


@dataclass(frozen=True)
class _Reference:
    relpath: str
    lineno: int
    enclosing_function: str | None  # None = module scope


def _tail(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


class _EnclosingFunctionVisitor(ast.NodeVisitor):
    """Walks a module tracking the innermost enclosing function, recording
    every reference to a name in *target_names*.

    A reference is either:

    * a direct/aliased NAME import of a target (``from ... import
      ledger_posture`` / ``... as x``), or
    * an attribute access ``<expr>.<target>`` where ``<expr>``'s own tail
      names the hosted_posture module OR is bound to it via a tracked
      import alias -- ``import specify_cli.core.hosted_posture as _hp`` /
      ``from specify_cli.core import hosted_posture as _hp2`` (review cycle
      1 / B3.2: a plain module-tail substring check misses both alias
      forms, since the accessed name is the alias, not ``hosted_posture``).
    """

    def __init__(self, relpath: str, target_names: frozenset[str], module_tail: str) -> None:
        self.relpath = relpath
        self.target_names = target_names
        self.module_tail = module_tail
        self.references: list[_Reference] = []
        self._stack: list[str] = []
        self._module_aliases: set[str] = set()

    def _current_function(self) -> str | None:
        return self._stack[-1] if self._stack else None

    def _record(self, lineno: int) -> None:
        self.references.append(_Reference(self.relpath, lineno, self._current_function()))

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802 - ast visitor API
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._visit_function(node)

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        # `import specify_cli.core.hosted_posture as _hp` -- record `_hp` as
        # a name bound to the hosted_posture module itself.
        for alias in node.names:
            dotted = alias.name
            if dotted == self.module_tail or dotted.endswith("." + self.module_tail):
                if alias.asname:
                    self._module_aliases.add(alias.asname)
                elif dotted == self.module_tail:
                    self._module_aliases.add(self.module_tail)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        module = node.module or ""
        module_is_hosted_posture = module.endswith(self.module_tail) or self.module_tail in module
        for alias in node.names:
            if module_is_hosted_posture and alias.name in self.target_names:
                # `from specify_cli.core.hosted_posture import ledger_posture[ as x]`
                self._record(node.lineno)
            elif alias.name == self.module_tail:
                # `from specify_cli.core import hosted_posture[ as _hp2]` --
                # importing the MODULE itself, not one of its functions.
                self._module_aliases.add(alias.asname or alias.name)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:  # noqa: N802
        if node.attr in self.target_names:
            value_tail = _tail(node.value)
            if value_tail is not None and (self.module_tail in value_tail or value_tail in self._module_aliases):
                self._record(node.lineno)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:  # noqa: N802
        if node.id in self.target_names:
            self._record(node.lineno)
        self.generic_visit(node)


def _find_references(source: str, relpath: str, target_names: frozenset[str] = _HOSTED_POSTURE_NAMES) -> list[_Reference]:
    tree = ast.parse(source)
    visitor = _EnclosingFunctionVisitor(relpath, target_names, _HOSTED_POSTURE_MODULE_TAIL)
    visitor.visit(tree)
    return visitor.references


def _assert_no_forbidden_reference(source: str, relpath: str) -> None:
    """The one assertion both the real forbidden-file/dir tests and their
    self-mutation check run (review cycle 1 / B3.2)."""
    offenders = _find_references(source, relpath)
    assert offenders == [], f"hosted_posture.ledger_posture/drain_posture must never be referenced from {relpath}: {offenders}"


def _assert_ledger_posture_allowlist(source: str, relpath: str, allowed: frozenset[str]) -> None:
    """The one assertion both the real status_transition.py allow-list test
    and its self-mutation check run (review cycle 1 / B3.1): the set of
    functions referencing ``ledger_posture`` must equal ``allowed`` exactly
    -- not merely "no offenders outside it", which stays green even when a
    permitted hook site's own reference is silently deleted."""
    references = _find_references(source, relpath, frozenset({"ledger_posture"}))
    referencing_functions = {ref.enclosing_function for ref in references if ref.enclosing_function is not None}
    module_scope_offenders = [ref for ref in references if ref.enclosing_function is None]
    assert module_scope_offenders == [], f"ledger_posture referenced at module scope in {relpath}: {module_scope_offenders}"
    assert referencing_functions == allowed, (
        f"functions referencing ledger_posture in {relpath} ({sorted(referencing_functions)}) "
        f"must equal the permitted T024 hook-site set ({sorted(allowed)}) exactly -- "
        "a missing entry means a hook site's wiring was silently removed; an extra "
        "entry means ledger_posture leaked to an unreviewed call site."
    )


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestLedgerFloor:
    def test_forbidden_files_carry_no_ledger_or_drain_posture_reference(self) -> None:
        for rel in _FORBIDDEN_FILES:
            path = _SRC_ROOT / rel
            assert path.exists(), f"expected file missing (test itself is stale): {path}"
            _assert_no_forbidden_reference(_read(path), rel)

    def test_forbidden_dirs_carry_no_ledger_or_drain_posture_reference(self) -> None:
        for rel_dir in _FORBIDDEN_DIRS:
            directory = _SRC_ROOT / rel_dir
            assert directory.is_dir(), f"expected directory missing (test itself is stale): {directory}"
            for path in sorted(directory.rglob("*.py")):
                _assert_no_forbidden_reference(_read(path), path.relative_to(_SRC_ROOT).as_posix())

    def test_status_transition_only_references_ledger_posture_at_permitted_hook_sites(self) -> None:
        path = _SRC_ROOT / _STATUS_TRANSITION_RELPATH
        assert path.exists(), f"expected file missing (test itself is stale): {path}"
        _assert_ledger_posture_allowlist(_read(path), _STATUS_TRANSITION_RELPATH, _ALLOWED_STATUS_TRANSITION_FUNCTIONS)

    def test_status_transition_does_not_reference_drain_posture(self) -> None:
        path = _SRC_ROOT / _STATUS_TRANSITION_RELPATH
        refs = _find_references(_read(path), _STATUS_TRANSITION_RELPATH, frozenset({"drain_posture"}))
        assert refs == []


class TestGuardBites:
    """Self-mutation checks: run the SAME assertion helpers the real tests
    run, against synthetic/mutated source, and prove they go red."""

    # -- B3.1: the allow-list check must be set-equality, not "no offenders" --

    def test_allowlist_helper_catches_a_module_scope_reference(self) -> None:
        """A reference outside every permitted function must be flagged."""
        planted = textwrap.dedent(
            """
            from specify_cli.core import hosted_posture

            _EAGER_ENABLED = hosted_posture.ledger_posture(None).enabled


            def _defer_fan_out(txn):
                if hosted_posture.ledger_posture(txn.repo_root).enabled:
                    pass


            def _fan_out_committed_coord_tail(stream):
                if hosted_posture.ledger_posture(None).enabled:
                    pass


            def emit_inner_state_changed_transactional(txn):
                if hosted_posture.ledger_posture(txn.repo_root).enabled:
                    pass
            """
        )
        with pytest.raises(AssertionError, match="module scope"):
            _assert_ledger_posture_allowlist(planted, _STATUS_TRANSITION_RELPATH, _ALLOWED_STATUS_TRANSITION_FUNCTIONS)

    def test_allowlist_helper_catches_a_removed_permitted_hook_site(self) -> None:
        """The exact regression M5 (review cycle 1) planted: two of the three
        real hook sites are removed. The real assertion helper -- the one
        `test_status_transition_only_references_ledger_posture_at_permitted_
        hook_sites` runs against live code -- must go red, not merely stay
        silent because no reference falls OUTSIDE the allow-list."""
        real_source = _read(_SRC_ROOT / _STATUS_TRANSITION_RELPATH)
        # Sanity: the real gate passes on real code before we mutate anything.
        _assert_ledger_posture_allowlist(real_source, _STATUS_TRANSITION_RELPATH, _ALLOWED_STATUS_TRANSITION_FUNCTIONS)

        without_two_sites = textwrap.dedent(
            """
            from specify_cli.core import hosted_posture


            def _defer_fan_out(txn):
                if hosted_posture.ledger_posture(txn.repo_root).enabled:
                    pass


            def _fan_out_committed_coord_tail(stream):
                pass


            def emit_inner_state_changed_transactional(txn):
                pass
            """
        )
        with pytest.raises(AssertionError, match="must equal the permitted"):
            _assert_ledger_posture_allowlist(without_two_sites, _STATUS_TRANSITION_RELPATH, _ALLOWED_STATUS_TRANSITION_FUNCTIONS)

    def test_allowlist_helper_catches_an_extra_unreviewed_site(self) -> None:
        """A NEW function referencing ledger_posture (leaked past review)
        must also be caught -- set equality cuts both ways."""
        planted = textwrap.dedent(
            """
            from specify_cli.core import hosted_posture


            def _defer_fan_out(txn):
                if hosted_posture.ledger_posture(txn.repo_root).enabled:
                    pass


            def _fan_out_committed_coord_tail(stream):
                if hosted_posture.ledger_posture(None).enabled:
                    pass


            def emit_inner_state_changed_transactional(txn):
                if hosted_posture.ledger_posture(txn.repo_root).enabled:
                    pass


            def _some_new_unreviewed_site(txn):
                if hosted_posture.ledger_posture(txn.repo_root).enabled:
                    pass
            """
        )
        with pytest.raises(AssertionError, match="must equal the permitted"):
            _assert_ledger_posture_allowlist(planted, _STATUS_TRANSITION_RELPATH, _ALLOWED_STATUS_TRANSITION_FUNCTIONS)

    # -- B3.2: import aliases of the hosted_posture module must not evade the scan --

    def test_forbidden_file_scan_catches_a_planted_reference(self) -> None:
        planted = textwrap.dedent(
            """
            from specify_cli.core import hosted_posture


            def materialize(feature_dir):
                if hosted_posture.ledger_posture(feature_dir).enabled:
                    pass
            """
        )
        with pytest.raises(AssertionError):
            _assert_no_forbidden_reference(planted, "specify_cli/status/reducer.py")

    def test_forbidden_dir_scan_catches_a_planted_reference(self) -> None:
        planted = textwrap.dedent(
            """
            from specify_cli.core.hosted_posture import drain_posture


            def record_decision():
                return drain_posture()
            """
        )
        with pytest.raises(AssertionError):
            _assert_no_forbidden_reference(planted, "specify_cli/decisions/ledger.py")

    @pytest.mark.parametrize(
        "aliased_import",
        [
            pytest.param("import specify_cli.core.hosted_posture as _hp", id="import-as"),
            pytest.param("from specify_cli.core import hosted_posture as _hp", id="from-import-as"),
        ],
    )
    def test_forbidden_file_scan_catches_a_module_import_alias(self, aliased_import: str) -> None:
        """B3.2: `import ... as _hp` / `from ... import hosted_posture as _hp`
        must not evade the forbidden-file scan, planted in a COPY of a real
        forbidden module's source (review's own wording)."""
        real_source = _read(_SRC_ROOT / "specify_cli/status/reducer.py")
        # Sanity: the real file is genuinely clean before mutation.
        _assert_no_forbidden_reference(real_source, "specify_cli/status/reducer.py")

        mutated = real_source + textwrap.dedent(
            f"""

            {aliased_import}


            def _leaked_ledger_check(feature_dir):
                return _hp.ledger_posture(feature_dir).enabled
            """
        )
        with pytest.raises(AssertionError):
            _assert_no_forbidden_reference(mutated, "specify_cli/status/reducer.py")

    def test_import_alias_does_not_evade_the_allowlist_check_either(self) -> None:
        """The same alias forms must still be attributed to the correct
        enclosing function inside status_transition.py's allow-list check
        (a `_hp.ledger_posture(...)` call inside a permitted function must
        still count as that function's reference, not go unseen)."""
        planted = textwrap.dedent(
            """
            import specify_cli.core.hosted_posture as _hp
            from specify_cli.core import hosted_posture as _hp2


            def _defer_fan_out(txn):
                if _hp.ledger_posture(txn.repo_root).enabled:
                    pass


            def _fan_out_committed_coord_tail(stream):
                if _hp2.ledger_posture(None).enabled:
                    pass


            def emit_inner_state_changed_transactional(txn):
                if _hp.ledger_posture(txn.repo_root).enabled:
                    pass
            """
        )
        # Must NOT raise: every permitted function references ledger_posture,
        # only through aliases, and the helper must still resolve them.
        _assert_ledger_posture_allowlist(planted, _STATUS_TRANSITION_RELPATH, _ALLOWED_STATUS_TRANSITION_FUNCTIONS)
