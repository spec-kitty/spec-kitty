"""WP03 / T019 — the death-spiral grep gate (SC-001 / NFR-004 / FR-004).

This is the keystone ratchet of mission ``single-planning-surface-authority``:
it proves that the ``coordination_branch is None ⇒ FLATTENED/COORDINATION`` /
``_coord_path.exists() ⇒ COORDINATION`` **topology/surface-inference** pattern has
**zero live decision sites** across ``src/``. After WP03 the mission shape is
READ from the WP02 stored :class:`MissionTopology`, never re-inferred ad-hoc from
the coordination-branch value or a disk ``stat`` — so all three historical
derivations are retired:

* ``mission_runtime/resolution.py`` (the door-internal ``_assemble_core_fragments``
  derivation);
* ``runtime/next/runtime_bridge.py`` (the ``_coord_path.exists()`` decision
  ladder);
* ``specify_cli/coordination/surface_resolver.py:resolve_status_surface_with_anchor``
  (the third, status-surface re-inference — INCLUDING the former
  ``coord_branch is None ⇒ PRIMARY`` gate, which the gate explicitly asserts is
  gone, alphonso/renata: a gate that passes while that site still classifies the
  surface is a vacuous-gate REJECTION).

The gate is **AST-based** (so comments / docstrings that merely *mention* the
idiom never trip it) and covers the negated / aliased spellings (renata N-2), not
just the literal ``coordination_branch is None``:

* ``coordination_branch is None`` / ``is not None`` / ``not coordination_branch``
  / ``if coordination_branch:`` (bare truthiness);
* the ``coord_branch`` alias in all the same forms;
* ``_coord_path.exists()`` / ``.exists()`` / ``.stat()`` on any ``*coord*`` path.

A test is flagged ONLY when such an inference test's enclosing branch **classifies
topology** — i.e. the branch body assigns a :class:`MissionTopology` / a
``decision_target`` kind, or returns a status-surface keyed on it. Pure
VALUE-reads (``coord_branch = str(raw) if raw else None``) and
the C-006 transient probe arms (the ``CoordState.DELETED`` / ``CoordState.EMPTY``
discrimination, the ``worktree_root`` materialization selection) are NOT
classifications and are not flagged.

Strictness (T031 / NFR-004): the gate carries a **negative-control** proving it
FAILS when a negated/aliased inference-classification site is reintroduced — a
gate that cannot fail is not a gate (the vacuous-grep REJECTION the prompt warns
against).
"""
from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import pytest

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_ROOT = _REPO_ROOT / "src"

# Names whose presence/absence/disk-state historically inferred topology.
_COORD_VALUE_NAMES: frozenset[str] = frozenset(
    {"coordination_branch", "coord_branch"}
)
_COORD_PATH_TOKEN = "coord"

# Tokens whose appearance in an inference branch body marks a TOPOLOGY/SURFACE
# CLASSIFICATION (as opposed to a value-read or a transient-state arm). The
# retired per-ref topology enum token is gone (FR-001b — the enum was deleted),
# so ``MissionTopology.`` is now the surviving classification target.
_CLASSIFICATION_TOKENS: tuple[str, ...] = (
    "MissionTopology.",
    "decision_target",
)

# The WP01 single 2×2-grid authority. A *relayed* spelling is a direct
# ``classify_topology(<coord-value-name>, …)`` call — bit-for-bit equivalent to
# the retired ``coordination_branch is None`` decision when it is the SOLE shape
# disposal (randy #2 / SC-001). It is FORBIDDEN as a live topology decision, and
# ALLOWED only as the un-backfilled FALLBACK arm of a function that FIRST reads
# the stored topology (so the stored shape disposes; the relay only derives once
# for a legacy mission carrying no stored ``topology``).
_CLASSIFY_TOPOLOGY_FN = "classify_topology"

# Markers proving the enclosing function reads the STORED topology before (or
# instead of) relaying: the canonical pure stored-topology readers + the stored
# enum-value membership probe. A function naming any of these has adopted the
# stored shape — its ``classify_topology(<coord>, …)`` call is the legitimate
# legacy fallback, not a parallel inference.
_STORED_TOPOLOGY_READ_MARKERS: tuple[str, ...] = (
    "read_topology",
    "stored_topology_from_meta",
    "stored_topology(",
    "MissionTopology.from_stored",
)

# The single SSOT derivation helper: ``backfill_topology._derive_topology`` is the
# ONE function whose entire job is to derive the shape from signals (consumed by
# BOTH the persisting ``ensure_topology`` and the pure ``read_topology``). It is
# the authority the relay-ban routes through, not a parallel inference — so it is
# allowlisted by name with this rationale.
_SSOT_DERIVATION_FUNCTIONS: frozenset[str] = frozenset({"_derive_topology"})


def _iter_src_python_files() -> list[Path]:
    return sorted(p for p in _SRC_ROOT.rglob("*.py") if "__pycache__" not in p.parts)


def _rel(path: Path) -> str:
    return path.relative_to(_REPO_ROOT).as_posix()


def _is_coord_value_name(node: ast.expr) -> bool:
    """True for a bare ``coordination_branch`` / ``coord_branch`` Name."""
    return isinstance(node, ast.Name) and node.id in _COORD_VALUE_NAMES


def _is_coord_path_exists_or_stat(node: ast.expr) -> bool:
    """True for ``<*coord*>.exists()`` / ``<*coord*>.stat()`` disk probes."""
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
        return False
    if node.func.attr not in ("exists", "stat"):
        return False
    receiver = node.func.value
    return isinstance(receiver, ast.Name) and _COORD_PATH_TOKEN in receiver.id.lower()


def _test_references_coord_inference(test: ast.expr) -> bool:
    """True when *test* is a coord value/disk inference in any aliased spelling.

    Covers: ``x is None`` / ``x is not None`` (Compare), ``not x`` (UnaryOp),
    bare truthiness ``if x:`` (a Name used directly as the test), boolean
    combinations (BoolOp), and ``*coord*.exists()/.stat()`` disk probes.
    """
    for node in ast.walk(test):
        if _is_coord_value_name(node):
            return True
        if _is_coord_path_exists_or_stat(node):
            return True
    return False


def _branch_classifies_topology(body: list[ast.stmt]) -> bool:
    """True when a branch body classifies topology (vs a value-read / transient).

    A classification assigns a ``MissionTopology`` / ``decision_target`` token.
    The C-006 transient arms (``CoordState.*``,
    ``worktree_root`` Path selection) and value-reads do not, so they never trip.
    """
    for stmt in body:
        snippet = ast.unparse(stmt)
        if any(token in snippet for token in _CLASSIFICATION_TOKENS):
            return True
    return False


def _live_inference_classification_sites(path: Path) -> list[int]:
    """Return line numbers of live coord-inference *classification* branches.

    Walks every ``if``/``elif`` and ternary (``IfExp``) whose test is a coord
    value/disk inference; flags it ONLY when the controlled branch classifies
    topology. Value-reads and transient-state arms are not classifications.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            if _test_references_coord_inference(node.test) and (
                _branch_classifies_topology(node.body)
                or _branch_classifies_topology(node.orelse)
            ):
                hits.append(node.lineno)
        elif isinstance(node, ast.IfExp) and _test_references_coord_inference(
            node.test
        ):
            # A ternary classifies when either arm names a classification token.
            body_src = ast.unparse(node.body) + " " + ast.unparse(node.orelse)
            if any(token in body_src for token in _CLASSIFICATION_TOKENS):
                hits.append(node.lineno)
    return hits


def _is_coord_value_arg(node: ast.expr) -> bool:
    """True for a ``coordination_branch`` / ``coord_branch`` arg (bare or attr).

    Covers both the bare ``classify_topology(coord_branch, …)`` and the attribute
    ``classify_topology(identity.coordination_branch, …)`` relay spellings.
    """
    if isinstance(node, ast.Name):
        return node.id in _COORD_VALUE_NAMES
    if isinstance(node, ast.Attribute):
        return node.attr in _COORD_VALUE_NAMES
    return False


def _function_reads_stored_topology(func: ast.AST) -> bool:
    """True when *func*'s body names a canonical stored-topology read marker."""
    src = ast.unparse(func)
    return any(marker in src for marker in _STORED_TOPOLOGY_READ_MARKERS)


def _live_relayed_classify_sites(path: Path) -> list[int]:
    """Return line numbers of live *relayed* ``classify_topology(<coord>, …)`` calls.

    The randy-#2 hardening (SC-001): a direct
    ``classify_topology(coordination_branch | coord_branch, …)`` call is the
    RELAYED spelling of the retired ``coordination_branch is None`` topology
    decision — equally a parallel inference when it is the sole shape disposal.
    It is flagged UNLESS its enclosing function FIRST reads the stored topology
    (``read_topology`` / ``stored_topology_from_meta`` / ``stored_topology`` /
    ``MissionTopology.from_stored``), in which case the relay is the legitimate un-backfilled-legacy
    fallback arm. The SSOT derivation helper ``_derive_topology`` is allowlisted by
    name (it IS the single authority the relay-ban routes through).
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits: list[int] = []
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if func.name in _SSOT_DERIVATION_FUNCTIONS:
            continue
        if _function_reads_stored_topology(func):
            # Adopted the stored shape — its relay call is the legacy fallback.
            continue
        for node in ast.walk(func):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == _CLASSIFY_TOPOLOGY_FN
                and node.args
                and _is_coord_value_arg(node.args[0])
            ):
                hits.append(node.lineno)
    return hits


# The three formerly-deriving modules MUST now show ZERO classification sites.
_FORMERLY_DERIVING_MODULES: tuple[str, ...] = (
    "src/mission_runtime/resolution.py",
    "src/runtime/next/runtime_bridge.py",
    "src/specify_cli/coordination/surface_resolver.py",
)


def test_zero_live_topology_inference_classification_sites() -> None:
    """No live ``coordination_branch``-None / ``_coord_path.exists()`` classifier.

    Across all of ``src/``, no ``if``/ternary keyed on the coord value/disk
    inference may classify topology. The shape is READ from the stored
    ``MissionTopology`` (FR-004 / SC-001). A new such site re-opens the
    parallel-inference death-spiral.
    """
    offenders: dict[str, list[int]] = {}
    for path in _iter_src_python_files():
        hits = _live_inference_classification_sites(path)
        if hits:
            offenders[_rel(path)] = hits
    assert not offenders, (
        "Live coordination_branch-None / _coord_path.exists() topology "
        f"CLASSIFICATION site(s) found: {dict(sorted(offenders.items()))}. The "
        "mission shape MUST be READ from the WP02 stored MissionTopology "
        "(mission_runtime.resolution.destination_kind_for_topology / "
        "ensure_topology), never re-inferred from the coordination-branch value "
        "or a disk stat (FR-004 / SC-001). Value-reads and the C-006 "
        "CoordState.DELETED/EMPTY transient arms are fine — only kind/topology "
        "classification keyed on the inference is forbidden."
    )


def test_zero_live_relayed_classify_topology_sites() -> None:
    """No live ``classify_topology(<coord-value>, …)`` relay disposes the shape.

    The randy-#2 hardening (SC-001 / NFR-004): a bare
    ``classify_topology(coordination_branch | coord_branch, has_lanes=False)`` call
    is bit-for-bit the retired ``coordination_branch is None`` decision relocated
    in name only — when it is the SOLE shape disposal, the "single authority" is a
    parallel inference, not an adoption of the STORED topology. Every such call
    across ``src/`` must be a legacy FALLBACK arm of a function that FIRST reads the
    stored topology (the read-the-stored-value-then-derive-once contract), or the
    SSOT ``_derive_topology`` helper itself. A bare relay re-opens the
    parallel-inference death-spiral.
    """
    offenders: dict[str, list[int]] = {}
    for path in _iter_src_python_files():
        hits = _live_relayed_classify_sites(path)
        if hits:
            offenders[_rel(path)] = hits
    assert not offenders, (
        "Live RELAYED classify_topology(<coordination_branch|coord_branch>, …) "
        f"site(s) found: {dict(sorted(offenders.items()))}. The mission shape MUST "
        "be READ from the WP02 stored MissionTopology (read_topology / "
        "stored_topology_from_meta); a direct classify_topology(coord_value, …) is "
        "the relocated-in-name-only ``coordination_branch is None`` inference (randy "
        "#2 / SC-001) unless it is the un-backfilled-legacy FALLBACK arm of a "
        "function that first reads the stored topology."
    )


def test_negative_control_relayed_classify_topology_is_caught() -> None:
    """Injection proof: the relay gate FAILS on a bare ``classify_topology`` relay.

    The synthetic offender disposes the surface shape SOLELY via
    ``classify_topology(coord_branch, has_lanes=False)`` with NO stored-topology
    read — the exact non-adoption randy flagged. The gate must catch it, or a
    grep-for-``is None`` would let the equivalent relay survive.
    """
    bad = textwrap.dedent(
        """
        from mission_runtime import classify_topology

        def rogue_surface_shape(coord_branch):
            # Relocated-in-name-only: no stored-topology read; the relay IS the
            # decision. Bit-for-bit the retired ``coord_branch is None`` inference.
            topology = classify_topology(coord_branch, has_lanes=False)
            return topology
        """
    )
    tmp = _REPO_ROOT / "src" / "__t019_relay_negative_control__.py"
    tmp.write_text(bad, encoding="utf-8")
    try:
        hits = _live_relayed_classify_sites(tmp)
    finally:
        tmp.unlink()
    assert hits, (
        "The relay gate failed to catch a bare classify_topology(coord_branch, …) "
        "relay with no stored-topology read — it is vacuous (NFR-004 / SC-001)."
    )


def test_relayed_classify_with_stored_read_is_not_flagged() -> None:
    """The legacy-fallback relay (after a stored read) is NOT flagged.

    Belt-and-braces: a function that FIRST reads the stored topology and only
    relays for the un-backfilled legacy case is the legitimate contract — it must
    pass, or the gate would force-fail the very pattern WP09 adopts.
    """
    benign = textwrap.dedent(
        """
        from mission_runtime import classify_topology
        from specify_cli.migration.backfill_topology import read_topology

        def adopts_stored_then_falls_back(feature_dir, coord_branch):
            try:
                return read_topology(feature_dir)
            except (FileNotFoundError, ValueError, OSError):
                # Un-backfilled legacy: derive ONCE from the value-read.
                return classify_topology(coord_branch, has_lanes=False)
        """
    )
    tmp = _REPO_ROOT / "src" / "__t019_relay_benign__.py"
    tmp.write_text(benign, encoding="utf-8")
    try:
        hits = _live_relayed_classify_sites(tmp)
    finally:
        tmp.unlink()
    assert hits == [], (
        f"A stored-read-then-fallback relay must not be flagged, got lines {hits}."
    )


def test_surface_resolver_600_gate_is_explicitly_covered() -> None:
    """The third derivation (surface_resolver) is in the swept set and is clean.

    Belt-and-braces against a vacuous gate: assert the surface resolver is one of
    the swept modules AND that it has zero classification sites — so the gate
    cannot pass while ``resolve_status_surface_with_anchor`` still decides the
    surface from ``coord_branch is None`` (the prompt's vacuous-gate REJECTION).
    """
    surface_resolver = _SRC_ROOT / "specify_cli/coordination/surface_resolver.py"
    assert surface_resolver.exists()
    assert _rel(surface_resolver) in _FORMERLY_DERIVING_MODULES
    assert _live_inference_classification_sites(surface_resolver) == []


def test_negative_control_gate_catches_reintroduced_classifier() -> None:
    """Injection proof (T031): the gate FAILS on a negated/aliased classifier.

    Proves the gate is not vacuous. The synthetic offender uses the ALIASED,
    NEGATED ``not coord_branch`` spelling (never the literal
    ``coordination_branch is None``) and a classification body — the gate must
    still catch it, or a grep-for-one-literal would let an equivalent inference
    survive.
    """
    bad = textwrap.dedent(
        """
        from mission_runtime import MissionTopology

        def rogue(coord_branch):
            if not coord_branch:
                # ALIASED + NEGATED reintroduction of the retired derivation.
                return MissionTopology.SINGLE_BRANCH
            return MissionTopology.COORD
        """
    )
    tmp = _REPO_ROOT / "src" / "__t019_negative_control__.py"
    tmp.write_text(bad, encoding="utf-8")
    try:
        hits = _live_inference_classification_sites(tmp)
    finally:
        tmp.unlink()
    assert hits, (
        "The T019 gate failed to catch a reintroduced negated/aliased "
        "(`not coord_branch` ⇒ MissionTopology) classifier — it is vacuous. A "
        "gate that cannot fail is not a gate (NFR-004 / SC-001)."
    )


def test_negative_control_ternary_classifier_is_caught() -> None:
    """The gate also catches a ternary (IfExp) inference classifier."""
    bad = textwrap.dedent(
        """
        from mission_runtime import MissionTopology

        def rogue(coordination_branch):
            shape = (
                MissionTopology.COORD
                if coordination_branch is not None
                else MissionTopology.SINGLE_BRANCH
            )
            return shape
        """
    )
    tmp = _REPO_ROOT / "src" / "__t019_negative_control_ternary__.py"
    tmp.write_text(bad, encoding="utf-8")
    try:
        hits = _live_inference_classification_sites(tmp)
    finally:
        tmp.unlink()
    assert hits, "The gate must catch a ternary coord-inference classifier."


def test_value_read_and_transient_arms_are_not_flagged() -> None:
    """Belt-and-braces: a value-read and a C-006 transient arm do NOT trip."""
    benign = textwrap.dedent(
        """
        def value_read(raw_coord):
            coord_branch = str(raw_coord) if raw_coord else None
            return coord_branch

        def transient_arm(_coord_path, feature_dir, resolved):
            # C-006 worktree-materialization selection (the surviving
            # runtime_bridge arm): a Path choice keyed on a *coord* disk stat,
            # but it assigns a Path, NOT a MissionTopology — so it is a transient
            # arm, not a topology classifier, and must NOT be flagged.
            worktree_root = _coord_path if _coord_path.exists() else resolved
            return worktree_root
        """
    )
    tmp = _REPO_ROOT / "src" / "__t019_benign__.py"
    tmp.write_text(benign, encoding="utf-8")
    try:
        hits = _live_inference_classification_sites(tmp)
    finally:
        tmp.unlink()
    assert hits == [], (
        f"Value-reads / transient arms must not be flagged as classifiers, "
        f"got lines {hits}."
    )
