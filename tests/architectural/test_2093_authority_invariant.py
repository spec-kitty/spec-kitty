"""FR-013 / #2093 — single-authority-per-field architectural invariant.

The WP-runtime-state eviction folds runtime-mutable WP state (``shell_pid``,
subtask completion, ``## Activity Log`` notes, ``tracker_refs``,
``agent``/``assignee``, review-cycle fields) out of ``tasks/WP##.md`` into the
append-only event log. #2093 is the split-brain this closes: a field must have
exactly ONE authority. This test is the enforcing net so the guarantee cannot
silently rot under a future refactor.

It asserts, in the **post-cutover single-authority end-state** (#2816 / IC-05:
the dual-write flag is retired, the reduced snapshot is the sole authority for
every runtime slot — data-model INV-2):

1. **No dynamic field is read from frontmatter as authority** — behavioral
   proof on the canonical ``WorkPackage`` reader: the reduced snapshot WINS
   over a divergent frontmatter value for every dynamic scalar slot, and an
   ABSENT snapshot entry is authoritative empty (``None``) — never a fallback
   to the frontmatter copy (C-001). Inverting the read (frontmatter as
   authority, or a frontmatter fallback) turns this red.

2. **No field is dual-homed** — the static authored schema
   (``FrontmatterManager.WP_FIELD_ORDER``) and the event-sourced slot set
   (``status.reducer._RUNTIME_SLOTS``) share only the explicitly TOLERATED
   migration-window cosmetic slots (deferred to IC-08). ``tracker_refs``
   (FR-006, struck from ``WP_FIELD_ORDER`` by WP07), ``notes`` and ``review``
   are purely event-sourced and MUST NOT appear in the static schema —
   re-homing any of them turns this red.

3. **ZERO frontmatter-authority reads survive on the reader path** — hardened
   two ways (#2816):
   (a) the reader-module set is **DERIVED** by AST-walking
   ``src/specify_cli/{status,cli,core,task_utils,dashboard}`` for BOTH classes
   of frontmatter runtime read — ``extract_scalar(..., "<dynamic field>")``
   AND typed attribute access ``read_wp_frontmatter(...).<dynamic field>``
   (the dashboard-scanner class research D-09 documents, invisible to the
   ``extract_scalar``-only detector). The tolerated set is now **empty**
   (FR-008): with WP04/WP05's reroutes complete, the derived union must be
   ``∅`` — a surviving reader of EITHER class is a real #2093 bypass and this
   goes red.
   (b) **ZERO** ``*_authority_active`` reader-authority gate remains anywhere
   on the reader path — the phase-1 dual-write gate was deleted (SC-002); the
   writer-side ``*_dual_write_*`` helpers and the lane-mirror gate
   (``_legacy_lane_mirror_enabled``, kept by C-004) are deliberately NOT
   reader-authority gates and are excluded by construction.

Non-vacuity (SC-003 / SC-009): because WP05 already rerouted every live reader
onto the snapshot, the live tree is clean — so both detector classes are proven
non-vacuous against **synthetic poison fixtures** reproducing the pre-reroute
patterns (the ``extract_scalar`` and the ``read_wp_frontmatter(...).<field>``
reads). A detector that can no longer discover a reintroduced bypass would be a
false green; the poison fixtures prove it still bites.

Refactor-stable: every arm keys on imported symbol / slot-name identity and
runtime behavior, never on line numbers or source text of a specific call.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

import specify_cli.status as _status_facade
from specify_cli.frontmatter import FrontmatterManager
from specify_cli.status.models import Lane, StatusEvent, WPInnerStateDelta
from spec_kitty_events.diary import _RUNTIME_SLOTS
from specify_cli.status.store import append_event
from specify_cli.task_utils import WorkPackage
from tests.architectural._ast_scan import parse_file

pytestmark = pytest.mark.architectural

# ---------------------------------------------------------------------------
# The field-authority table (data-model.md), encoded as symbol identity.
# ---------------------------------------------------------------------------

#: The dynamic runtime-state slot set — the event log is the sole authority for
#: these. Imported straight from the reducer (single source of truth).
_EVENT_SLOTS: frozenset[str] = frozenset(_RUNTIME_SLOTS)

#: The migration-window cosmetic slots still emitted into the authored schema.
#: Their removal from ``WP_FIELD_ORDER`` is the DEFERRED IC-08 post-cutover
#: reduction — tolerated here, NOT a dual-home authority (the frontmatter copy
#: is a mirror, the snapshot is the authority; arm 1 proves it).
_TOLERATED_MIGRATION_WINDOW_SLOTS: frozenset[str] = frozenset(
    {"subtasks", "assignee", "agent", "shell_pid", "shell_pid_created_at"}
)


def _feature_with_divergent_frontmatter(tmp_path: Path) -> tuple[Path, Path]:
    """Build a minimal ``kitty-specs/<slug>`` feature dir + WP file.

    Frontmatter deliberately carries DIVERGENT dynamic values so arm 1 can tell
    which home won. ``status_phase: 1`` is written only as the retained cutover
    marker (C-004 lane mirror); the runtime reader is unconditional and no
    longer keys on it. Returns ``(feature_dir, wp_file)``.
    """
    slug = "001-authority-invariant"
    feature_dir = tmp_path / "kitty-specs" / slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01AUTHORITYINVARIANT00000",
                "mid8": "01AUTHOR",
                "mission_slug": slug,
                "mission_type": "software-dev",
                "status_phase": "1",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    wp_file = tasks_dir / "WP01-core.md"
    wp_file.write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Core\n"
        "agent: frontmatter-agent\n"
        "assignee: frontmatter-assignee\n"
        "shell_pid: '11111'\n"
        "---\n\n# WP01\n",
        encoding="utf-8",
    )
    return feature_dir, wp_file


def _make_work_package(wp_file: Path) -> WorkPackage:
    content = wp_file.read_text(encoding="utf-8")
    _, _, body = content.partition("---\n")
    front, _, body_text = body.partition("\n---\n")
    return WorkPackage(
        feature="001-authority-invariant",
        path=wp_file,
        current_lane="claimed",
        relative_subpath=Path("tasks/WP01-core.md"),
        frontmatter=front,
        body=body_text,
        padding="",
    )


# ===========================================================================
# Arm 1 — no dynamic field is read from frontmatter as AUTHORITY
# ===========================================================================


def test_snapshot_is_authority_over_frontmatter(tmp_path: Path) -> None:
    """The reduced snapshot is the UNCONDITIONAL authority (C-001): it WINS over
    a divergent frontmatter value for every dynamic scalar slot. Inverting the
    read (frontmatter as authority) turns this red — the #2093 split-brain."""
    feature_dir, wp_file = _feature_with_divergent_frontmatter(tmp_path)

    # Claim rides the transition policy_metadata (agent/shell_pid); assignee is
    # an off-axis annotation. All DIVERGE from the frontmatter values above.
    append_event(
        feature_dir,
        StatusEvent(
            event_id="seed-claim",
            mission_slug="001-authority-invariant",
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-01-01T00:00:01+00:00",
            actor="fixture",
            force=True,
            execution_mode="worktree",
            policy_metadata={"shell_pid": 99999, "agent": "snapshot-agent"},
        ),
    )
    from specify_cli.status.emit import emit_inner_state_changed

    emit_inner_state_changed(
        feature_dir,
        "WP01",
        WPInnerStateDelta(assignee="snapshot-assignee"),
        actor="fixture",
        mission_slug="001-authority-invariant",
        at="2026-01-01T00:00:02+00:00",
        repo_root=tmp_path,
    )

    wp = _make_work_package(wp_file)
    assert wp.agent == "snapshot-agent", "agent authority is frontmatter, not the event log (#2093)"
    assert wp.shell_pid == "99999", "shell_pid authority is frontmatter, not the event log (#2093)"
    assert wp.assignee == "snapshot-assignee", "assignee authority is frontmatter, not the event log (#2093)"


def test_absent_snapshot_entry_is_authoritative_empty_not_frontmatter_fallback(
    tmp_path: Path,
) -> None:
    """C-001 positive control: when the snapshot carries NO runtime entry for a
    WP, the reader returns authoritative empty (``None``) — it does NOT fall back
    to the frontmatter value. This is the post-cutover replacement for the
    retired flag-OFF frontmatter fallback: it proves arm 1's snapshot-wins result
    is unconditional, not a coincidence of the reader happening to read the event
    log while a fallback path still exists."""
    feature_dir, wp_file = _feature_with_divergent_frontmatter(tmp_path)

    # A real, non-empty event log that carries NO WP01 runtime state (the event
    # is for an unrelated WP): WP01's snapshot slots are genuinely absent, so a
    # frontmatter fallback — if one survived — would surface the divergent
    # frontmatter values below.
    append_event(
        feature_dir,
        StatusEvent(
            event_id="seed-other",
            mission_slug="001-authority-invariant",
            wp_id="WP99",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-01-01T00:00:01+00:00",
            actor="fixture",
            force=True,
            execution_mode="worktree",
            policy_metadata={"shell_pid": 99999, "agent": "snapshot-agent"},
        ),
    )

    wp = _make_work_package(wp_file)
    assert wp.agent is None, "absent snapshot entry must NOT fall back to frontmatter 'agent' (C-001)"
    assert wp.shell_pid is None, "absent snapshot entry must NOT fall back to frontmatter 'shell_pid' (C-001)"
    assert wp.assignee is None, "absent snapshot entry must NOT fall back to frontmatter 'assignee' (C-001)"


# ===========================================================================
# Arm 2 — no field is dual-homed (static schema ∩ event-slot set)
# ===========================================================================


def test_no_field_is_dual_homed_static_and_event() -> None:
    """``WP_FIELD_ORDER`` ∩ ``_RUNTIME_SLOTS`` == exactly the tolerated
    migration-window cosmetic slots. ``tracker_refs``/``notes``/``review`` are
    purely event-sourced and MUST NOT appear in the static authored schema."""
    static_schema = set(FrontmatterManager.WP_FIELD_ORDER)
    dual_homed = static_schema & set(_EVENT_SLOTS)

    unexpected = dual_homed - _TOLERATED_MIGRATION_WINDOW_SLOTS
    assert not unexpected, (
        "field(s) dual-homed in BOTH the static authored schema (WP_FIELD_ORDER) "
        f"and the event-sourced slot set — a #2093 split-brain: {sorted(unexpected)}"
    )

    # The eviction targets must be gone from the static schema (bites on a
    # regression that re-authors them).
    for evicted in ("tracker_refs", "notes", "review"):
        assert evicted not in static_schema, (
            f"{evicted!r} is event-sourced (FR-006/SC-004/FR-009) and must NOT be "
            "re-listed in WP_FIELD_ORDER (dual-home regression)"
        )

    # The tolerated set is a genuine subset of the event slots (guards a typo
    # that would make the arm vacuous).
    assert set(_EVENT_SLOTS) >= _TOLERATED_MIGRATION_WINDOW_SLOTS


# ===========================================================================
# Arm 3 — ZERO frontmatter-authority reads survive on the reader path
# ===========================================================================
#
# Hardened (#2816): the reader-module set is DERIVED (AST-walk for BOTH
# dynamic-field ``extract_scalar`` reads AND ``read_wp_frontmatter(...).<field>``
# attribute reads), the tolerated set is EMPTY (FR-008), and ZERO
# ``*_authority_active`` reader gate remains (the phase-1 gate is deleted).

#: The dynamic runtime-state fields whose authority is the event log
#: (data-model.md). A frontmatter read of any of these — via ``extract_scalar``
#: OR ``read_wp_frontmatter(...).<field>`` attribute access — is a
#: reader-authority site the invariant tracks. Authored-intent fields
#: (``role``, ``agent_profile``, ``model`` authored recommendation) are
#: deliberately EXCLUDED: they stay frontmatter-canonical (D-09 / C-008); only
#: the resolved-actual identity is event-sourced (WP10/WP11).
#: ``verdict`` (WP05, verdict-seam-write-unification-01KZ9Q35, FR-004/T027)
#: extends this set to the review-cycle-artifact verdict field: an
#: ``extract_scalar(..., "verdict")`` read is now ALSO an authority bypass,
#: not just the WP-runtime-state fields below. This mission's own reader
#: collapse retired every LIVE call of that shape
#: (``tasks_parsing_validation.py::_get_latest_review_cycle_verdict``,
#: ``agent_utils/status.py::_get_wp_review_verdict``); adding it here turns
#: this the enforcing ratchet against reintroduction.
_DYNAMIC_RUNTIME_FIELDS: frozenset[str] = frozenset(
    {
        "agent",
        "assignee",
        "shell_pid",
        "shell_pid_created_at",
        "tracker_refs",
        "reviewer",
        "reviewer_agent",
        "reviewer_shell_pid",
        "review_status",
        "reviewed_by",
        "approved_by",
        "review_feedback",
        "verdict",
    }
)

#: The call names whose ``(...).<dynamic field>`` attribute chain is a typed
#: frontmatter runtime read (research D-09: the dashboard scanner read
#: ``read_wp_frontmatter(...).agent`` — invisible to the ``extract_scalar``
#: detector). Keyed on the read-call anchor so a snapshot read
#: (``wp_snapshot_state(...).agent``) is NOT flagged.
_FRONTMATTER_READ_CALLS: frozenset[str] = frozenset({"read_wp_frontmatter"})

#: The reader-authority roots walked for the derivation. ``dashboard`` is
#: included (#2816) so the D-09 scanner class — the motivating pre-reroute
#: bypass — is actually covered: re-pointing a snapshot read there back to
#: ``read_wp_frontmatter(...).<field>`` must turn this invariant red.
#: ``agent_utils``/``review``/``post_merge`` (WP05, T027) extend coverage to
#: the review-cycle-verdict reader family this mission collapsed
#: (``agent_utils/status.py::show_kanban_status``,
#: ``review/artifacts.py``'s retired verdict-parser pair,
#: ``post_merge/review_artifact_consistency.py``'s merge gate).
_READER_AUTHORITY_ROOTS = (
    "status",
    "cli",
    "core",
    "task_utils",
    "dashboard",
    "agent_utils",
    "review",
    "post_merge",
)

#: The tolerated set of modules that legitimately read a dynamic runtime field
#: from frontmatter. Post-cutover (FR-008 / IC-05) this is EMPTY: WP04 deleted
#: the dual-write flag and WP05 rerouted every reader (dashboard scanner,
#: ``workflow_cores`` review read, ``tasks_move_task`` ownership read) onto the
#: snapshot. ANY module in the AST-derived set is now a real #2093 bypass — the
#: derived union MUST equal this empty set.
_SANCTIONED_READER_MODULES: frozenset[str] = frozenset()


# ---------------------------------------------------------------------------
# Arm 4 (WP05/T027, FR-004) — review-cycle-*.md verdict-frontmatter glob
# detector.
#
# A THIRD, independent detector class from arm 3's two (``extract_scalar``
# and ``read_wp_frontmatter(...).<field>``): it targets a review-cycle
# ARTIFACT frontmatter read for the "verdict" field specifically -- a module
# that BOTH globs ``review-cycle-*.md`` AND reads a "verdict" value is the
# exact shape the two retired verdict-parser functions
# (``latest_review_artifact_verdict`` / ``rejected_review_artifact_for_
# terminal_lane`` in ``review/artifacts.py``, ``_get_latest_review_cycle_
# verdict`` in ``tasks_parsing_validation.py``, ``_get_wp_review_verdict`` in
# ``agent_utils/status.py``) used. Neither signal alone is suspicious (a glob
# for cycle-numbering purposes, or an unrelated ``.verdict`` access, is
# legitimate) -- only the CO-OCCURRENCE is the bypass, mirroring the WP04
# vocab bridge guard's own co-occurring-literals idiom
# (``test_verdict_vocab_single_source.py::_co_occurring_equivalence_modules``).
# ---------------------------------------------------------------------------

_REVIEW_CYCLE_GLOB_LITERAL = "review-cycle-*.md"

#: Call names whose direct ``(...).verdict`` attribute chain is a review-cycle
#: verdict read (``ReviewCycleArtifact.from_file(...).verdict`` /
#: ``ReviewCycleArtifact.latest(...).verdict``). Deliberately does NOT flag
#: ``.from_file``/``.latest`` accessing any OTHER attribute (``.body``,
#: ``.cycle_number``) -- those are the KEPT content/cycle-number loader uses
#: (squad #1: fix-mode prose, arbiter cycle_number), not verdict reads.
_REVIEW_CYCLE_LOAD_CALLS: frozenset[str] = frozenset({"from_file", "latest"})


def _globs_review_cycle_files(tree: ast.AST) -> bool:
    """True if the module calls ``<expr>.glob("review-cycle-*.md")`` (or
    ``.rglob``) anywhere -- the review-cycle-artifact-directory scan
    signature."""
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("glob", "rglob")
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == _REVIEW_CYCLE_GLOB_LITERAL
        ):
            return True
    return False


def _reads_verdict_field(tree: ast.AST) -> bool:
    """True if the module reads a "verdict" value via
    ``extract_scalar(<any>, "verdict")`` or a direct ``.verdict`` attribute
    chained off a ``from_file(...)``/``latest(...)`` call."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_extract_scalar_verdict_call_generic(node):
            return True
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "verdict"
            and isinstance(node.value, ast.Call)
        ):
            func = node.value.func
            call_name = (
                func.attr
                if isinstance(func, ast.Attribute)
                else func.id
                if isinstance(func, ast.Name)
                else None
            )
            if call_name in _REVIEW_CYCLE_LOAD_CALLS:
                return True
    return False


def _is_extract_scalar_verdict_call_generic(node: ast.Call) -> bool:
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else None
    if name != "extract_scalar" or len(node.args) < 2:
        return False
    field_arg = node.args[1]
    return isinstance(field_arg, ast.Constant) and field_arg.value == "verdict"


def _reads_review_cycle_verdict_via_glob(tree: ast.AST) -> bool:
    """Co-occurrence signature (WP05/T027): a module that BOTH globs
    ``review-cycle-*.md`` AND reads a "verdict" value is a review-cycle
    verdict-authority bypass."""
    return _globs_review_cycle_files(tree) and _reads_verdict_field(tree)


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "src" / "specify_cli").is_dir():
            return parent
    raise AssertionError("could not locate repo root from test file")


def _iter_root_modules(root: Path) -> list[Path]:
    modules: list[Path] = []
    for pkg in _READER_AUTHORITY_ROOTS:
        modules.extend(sorted((root / "src" / "specify_cli" / pkg).rglob("*.py")))
    return modules


def _reads_dynamic_field_via_extract_scalar(tree: ast.AST) -> bool:
    """True if the module calls ``extract_scalar(<any>, "<dynamic field>")``."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else None
        if name != "extract_scalar" or len(node.args) < 2:
            continue
        field_arg = node.args[1]
        if isinstance(field_arg, ast.Constant) and field_arg.value in _DYNAMIC_RUNTIME_FIELDS:
            return True
    return False


def _is_frontmatter_attr_read(node: ast.AST) -> bool:
    """True for a ``read_wp_frontmatter(...).<runtime_field>`` attribute read.

    The robust anchor from research D-09: an ``ast.Attribute`` whose ``.value``
    is a direct call to ``read_wp_frontmatter`` (bare name or ``module.``
    attribute form) and whose attribute name is a dynamic runtime field. It does
    NOT match a snapshot-sourced read (``wp_snapshot_state(...).agent``) nor an
    authored-intent field (``.agent_profile``) — no type inference, no
    false-positive on the legitimate authored frontmatter reads the dashboard
    still performs (``role``/``agent_profile``/``model``)."""
    if not isinstance(node, ast.Attribute):
        return False
    if node.attr not in _DYNAMIC_RUNTIME_FIELDS:
        return False
    base = node.value
    if not isinstance(base, ast.Call):
        return False
    func = base.func
    call_name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else None
    return call_name in _FRONTMATTER_READ_CALLS


def _reads_dynamic_field_via_attribute_access(tree: ast.AST) -> bool:
    """True if the module reads a dynamic runtime field via typed attribute
    access on a ``read_wp_frontmatter(...)`` result (the D-09 dashboard class)."""
    return any(_is_frontmatter_attr_read(node) for node in ast.walk(tree))


def _derive_reader_authority_modules(root: Path) -> set[str]:
    """AST-derived reader modules — the hardened replacement for the old
    hardcoded tuple. Any module under the reader roots that reads a dynamic
    runtime field from frontmatter, via ``extract_scalar``,
    ``read_wp_frontmatter(...).<field>`` attribute access, OR the WP05/T027
    review-cycle-*.md glob+verdict co-occurrence, is a reader-authority
    site; a NEW one of any class auto-joins."""
    derived: set[str] = set()
    for path in _iter_root_modules(root):
        tree = parse_file(path)
        if (
            _reads_dynamic_field_via_extract_scalar(tree)
            or _reads_dynamic_field_via_attribute_access(tree)
            or _reads_review_cycle_verdict_via_glob(tree)
        ):
            derived.add(path.relative_to(root).as_posix())
    return derived


def _referenced_authority_gates(tree: ast.AST) -> set[str]:
    """Referenced identifiers that play a snapshot-vs-frontmatter READER-AUTHORITY
    gate role — name ends with ``_authority_active``. Post-cutover there should be
    ZERO such gate (the phase-1 dual-write gate was deleted, SC-002). Writer-side
    ``*_dual_write_*`` helpers and the lane-mirror (``_legacy_lane_mirror_enabled``,
    kept by C-004) are NOT reader-authority gates and are excluded by
    construction so this arm tracks the ONE reader concern."""
    gates: set[str] = set()
    for node in ast.walk(tree):
        name: str | None = None
        if isinstance(node, ast.Name):
            name = node.id
        elif isinstance(node, ast.Attribute):
            name = node.attr
        elif isinstance(node, ast.FunctionDef):
            name = node.name
        if name and name.endswith("_authority_active"):
            gates.add(name)
    return gates


def test_phase1_gate_is_deleted_from_the_status_facade() -> None:
    """SC-002 post-cutover fact: the phase-1 dual-write reader-authority gate
    (``phase1_snapshot_authority_active``) is GONE from the ``specify_cli.status``
    facade — neither an attribute nor an ``__all__`` export. WP04 deleted the
    predicate; re-adding it (a resurrected dual-write reader gate) turns this
    red."""
    assert not hasattr(_status_facade, "phase1_snapshot_authority_active"), (
        "the phase-1 dual-write authority gate was resurrected on the status "
        "facade — the reader path must have ZERO frontmatter-authority gate (SC-002)"
    )
    assert "phase1_snapshot_authority_active" not in getattr(_status_facade, "__all__", [])


def test_no_reader_authority_gate_remains() -> None:
    """Across every module under the reader-authority roots, ZERO
    ``*_authority_active`` reader gate remains post-cutover. The canonical
    phase-1 gate was deleted (SC-002); a differently-named second authority gate
    (a resurrected reader split-brain) turns this red. Writer-side dual-write /
    lane-mirror gates are excluded by construction."""
    root = _repo_root()
    discovered: set[str] = set()
    for path in _iter_root_modules(root):
        tree = parse_file(path)
        discovered |= _referenced_authority_gates(tree)

    assert discovered == set(), (
        "a *_authority_active reader-authority gate survives post-cutover: "
        f"{sorted(discovered)} — the #2093 reader split-brain must have EXACTLY "
        "ZERO reader-authority gates after the frontmatter-read eviction (SC-002)"
    )


def test_no_frontmatter_authority_reader_survives() -> None:
    """The AST-DERIVED set of dynamic-field frontmatter readers — union of
    ``extract_scalar`` reads AND ``read_wp_frontmatter(...).<field>`` attribute
    reads — must be EMPTY (the tolerated set is ``frozenset()``, FR-008). A module
    reading a runtime field from frontmatter by EITHER class is a #2093 bypass and
    trips this. This is INV-2's enforcing net: after cutover, every runtime read
    resolves the snapshot."""
    root = _repo_root()
    derived = _derive_reader_authority_modules(root)

    new_bypass = derived - _SANCTIONED_READER_MODULES
    assert not new_bypass, (
        "a module reads a dynamic runtime field from frontmatter (via extract_scalar "
        f"or read_wp_frontmatter(...).<field>) — a #2093 bypass: {sorted(new_bypass)}. "
        "Route the read through the snapshot seam (WorkPackage / wp_snapshot_state) "
        "so the reduced snapshot is the sole authority (INV-2)."
    )


# ---------------------------------------------------------------------------
# Detector non-vacuity (SC-003 / SC-009) — proven against SYNTHETIC poison.
#
# WP05 already rerouted every live reader onto the snapshot, so the live tree is
# clean (the three arms above assert that end-state). A detector that discovers
# nothing on a clean tree tells you nothing about whether it CAN discover — so we
# prove both detector classes still bite against synthetic sources reproducing
# the pre-reroute patterns. A future refactor that neuters a detector (making the
# invariant a false green) turns these red.
# ---------------------------------------------------------------------------


def test_detector_flags_extract_scalar_frontmatter_read() -> None:
    """SC-003 non-vacuity for the ``extract_scalar`` arm: a reintroduced
    ``extract_scalar(front, "agent")`` frontmatter authority read is flagged RED;
    a non-runtime (authored/structural) field read is GREEN."""
    poison = 'def f(front):\n    return extract_scalar(front, "agent")\n'
    assert _reads_dynamic_field_via_extract_scalar(ast.parse(poison)) is True

    ok = 'def f(front):\n    return extract_scalar(front, "work_package_id")\n'
    assert _reads_dynamic_field_via_extract_scalar(ast.parse(ok)) is False


def test_detector_flags_dashboard_style_frontmatter_attribute_read() -> None:
    """SC-009 non-vacuity for the attribute-access arm — the crux of #2816.

    The dashboard scanner (``dashboard/scanner.py::_process_wp_file``) read
    runtime ``agent``/``assignee`` via ``read_wp_frontmatter(...).<attr>`` — typed
    attribute access on ``WPMetadata``, never ``extract_scalar`` — so it escaped
    the original detector (research D-09). WP05 rerouted the live scanner onto the
    snapshot, so this is proven against a SYNTHETIC source reproducing the
    pre-reroute pattern: the extended detector MUST flag it RED, and a
    snapshot-sourced read GREEN. A detector that stays green on the poison is a
    false green that defeats the mission."""
    poison = "def f(front):\n    return read_wp_frontmatter(front).agent\n"
    assert _reads_dynamic_field_via_attribute_access(ast.parse(poison)) is True

    # The ``module.read_wp_frontmatter(...).field`` method-call form is also RED.
    poison_method = (
        "import m\n"
        "def f(front):\n"
        "    return m.read_wp_frontmatter(front).assignee\n"
    )
    assert _reads_dynamic_field_via_attribute_access(ast.parse(poison_method)) is True

    # Mirror control: a snapshot-sourced read is GREEN — the extension keys on the
    # frontmatter read-call anchor, not a blanket ``.agent`` matcher.
    snapshot_read = "def f(fd, wp):\n    return wp_snapshot_state(fd, wp).agent\n"
    assert _reads_dynamic_field_via_attribute_access(ast.parse(snapshot_read)) is False

    # C-008 control: an authored-intent field (``agent_profile``) read from
    # frontmatter is GREEN — it stays frontmatter-canonical, not event-sourced.
    authored_read = "def f(front):\n    return read_wp_frontmatter(front).agent_profile\n"
    assert _reads_dynamic_field_via_attribute_access(ast.parse(authored_read)) is False


def test_detector_flags_review_cycle_glob_verdict_frontmatter_read() -> None:
    """SC-002/SC-003 non-vacuity for the review-cycle-*.md glob arm (WP05/T027):
    a synthetic module reproducing the retired verdict-parser shape (glob +
    ``extract_scalar(..., "verdict")``, or glob + ``.from_file(...).verdict`` /
    ``.latest(...).verdict``) is flagged RED; a module that globs WITHOUT
    reading verdict (cycle numbering), or reads an unrelated field, is GREEN."""
    poison_extract = (
        "def f(wp_dir):\n"
        "    cycles = sorted(wp_dir.glob('review-cycle-*.md'))\n"
        "    return extract_scalar(cycles[-1].read_text(), 'verdict')\n"
    )
    assert _reads_review_cycle_verdict_via_glob(ast.parse(poison_extract)) is True

    poison_from_file = (
        "def f(wp_dir):\n"
        "    candidates = wp_dir.glob('review-cycle-*.md')\n"
        "    return ReviewCycleArtifact.from_file(candidates[-1]).verdict\n"
    )
    assert _reads_review_cycle_verdict_via_glob(ast.parse(poison_from_file)) is True

    poison_latest = (
        "def f(wp_dir):\n"
        "    _ = wp_dir.glob('review-cycle-*.md')\n"
        "    return ReviewCycleArtifact.latest(wp_dir).verdict\n"
    )
    assert _reads_review_cycle_verdict_via_glob(ast.parse(poison_latest)) is True

    # Glob-only control (cycle numbering, existence check): GREEN.
    glob_only = "def f(wp_dir):\n    return len(list(wp_dir.glob('review-cycle-*.md')))\n"
    assert _reads_review_cycle_verdict_via_glob(ast.parse(glob_only)) is False

    # verdict-access-only control (no glob at all): GREEN — the co-occurrence
    # is the bypass signature, not either signal alone.
    verdict_only_no_glob = "def f(artifact):\n    return artifact.verdict\n"
    assert _reads_review_cycle_verdict_via_glob(ast.parse(verdict_only_no_glob)) is False

    # squad #1 control: the KEPT content loaders' legitimate attribute access
    # (``.body``/``.cycle_number``, never ``.verdict``) stays GREEN even when
    # co-located with a glob in the same function.
    kept_content_loader = (
        "def f(wp_dir):\n"
        "    _ = wp_dir.glob('review-cycle-*.md')\n"
        "    return ReviewCycleArtifact.latest(wp_dir).cycle_number\n"
    )
    assert _reads_review_cycle_verdict_via_glob(ast.parse(kept_content_loader)) is False


#: NOTE: the real-tree, post-collapse proof for arm 4 (no module both globs
#: ``review-cycle-*.md`` and reads "verdict") is NOT a separate test -- arm 4
#: is folded directly into :func:`_derive_reader_authority_modules` (the
#: SAME union :func:`test_no_frontmatter_authority_reader_survives` already
#: asserts is empty), so that existing end-state assertion covers all three
#: detector classes at once rather than duplicating the real-tree walk here.
