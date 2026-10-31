"""Architectural regression guard: untrusted-path containment (FR-005 / SC-006).

WP04 — anchored on the WP01 audited-surface inventory.

What this guard does
--------------------
1. **Inventory integrity (T018/T019-b):** asserts that the WP01 audit still
   passes against the current source tree — any new *undispositioned*
   untrusted-segment join introduced into an audited surface causes the audit
   to report a missing-inventory error, which this test surfaces as a failure.

2. **Seam-presence check (T018):** for every surface classified
   ``routed-through-seam`` in the inventory, re-inspects that file's AST and
   asserts that at least one canonical seam name is referenced.  A developer
   who removes the seam call while keeping the path join would be caught here
   (the inventory still expects the seam; a file with a join but no seam
   reference fails this assertion).

3. **Non-empty coverage assertion (T019-b):** asserts the set of
   ``routed-through-seam`` surfaces inspected is non-empty and equals the
   set declared in the inventory.  A vacuous guard that inspects zero files
   passes no assertions — this assertion defeats that failure mode.

4. **FR-009 presence (T018):** asserts the inventory still contains an
   entry for the ``mission_metadata.py`` write-path (the inventory-only FR-009
   assertion that ``audit.py`` enforces via its check 4).

Anchoring strategy
------------------
This test imports ``audit.py``'s public helpers (``discover_rows``,
``_parse_inventory_rows``, ``INVENTORY_PATH``, ``SRC_ROOT``) rather than
duplicating the matcher.  The inventory is the single source of truth for
dispositions; the guard re-runs the live discovery and cross-checks it against
the inventory.

T019 real-code mutation proof (recorded in handoff)
----------------------------------------------------
Mutation (a): a throwaway ``_ = root / mission_slug`` was temporarily inserted
into ``src/specify_cli/status/store.py`` (after line 200, within the
``_is_contained`` method).  The audit discovered the new join and ``audit.py``
exited non-zero with "discovered sink … is MISSING from inventory.md" —
proving the guard reads real surfaces.  After reverting, ``audit.py`` exited 0
and this test passes.

Mutation (b): this test's ``assert len(seam_surface_paths) > 0`` assertion
catches a vacuous run (zero surfaces inspected), and
``assert seam_surface_paths == expected_seam_surfaces`` catches inventory
drift (new surfaces added or existing surfaces removed without updating this
guard).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# ``untrusted_path_audit`` is a sibling package (``__init__.py`` present).
# mypy resolves it via the tests/ conftest.py rootdir; the import is a plain
# package import — no sys.path manipulation needed.
# ---------------------------------------------------------------------------
_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parents[2]

from tests.architectural._ratchet_keys import composite_key
from tests.architectural.untrusted_path_audit.audit import (
    INVENTORY_ONLY_TAG,
    INVENTORY_PATH,
    SRC_ROOT,
    _parse_inventory_rows,
    build_discovered_key_map,
    build_inventory_key_map,
    check_overcount,
    check_undercount,
    discover_rows,
    main as _audit_main,
    truncate_token,
)

pytestmark = pytest.mark.architectural

# ---------------------------------------------------------------------------
# Canonical seam names (FR-001 / FR-002).
#
# Includes the primary seam functions AND the known boundary delegators that
# route untrusted segments to the seam indirectly (e.g. ``materialize`` calls
# ``safe_mission_slug`` internally; ``_validate_segment`` delegates to
# ``assert_safe_path_segment``).  A file that references any of these is
# considered to route through the seam.
# ---------------------------------------------------------------------------
_SEAM_NAMES: frozenset[str] = frozenset(
    {
        # Primary seam functions — core/paths.py
        "assert_safe_path_segment",
        "safe_mission_slug",
        # Containment seam — core/utils.py
        "ensure_within_any",
        "ensure_within_directory",
        "write_text_within_directory",
        # Boundary delegators (each calls a primary seam internally)
        "_validate_mission_slug",  # status/aggregate.py → assert_safe_path_segment
        "_validate_segment",  # review/cycle.py → assert_safe_path_segment
        "_is_safe_slug",  # status/store.py → assert_safe_path_segment
        # cli/commands/decision.py raw-token path-traversal reject at the CLI
        # boundary (^[A-Za-z0-9][A-Za-z0-9_-]*$, rejecting ../ before any join).
        # #5019: after decision.py's ledger read moved off
        # resolve_handle_to_read_path onto placement_seam(...).read_dir(
        # PRIMARY_METADATA), this regex is the in-file guard; the seam it now
        # calls is itself assert_safe_path_segment-guarded.
        "_SAFE_SLUG_RE",
        "resolve_handle_to_read_path",  # missions/_read_path_resolver.py → assert_safe_path_segment (#2037 decision.py)
        # Reducer delegators: these produce a pre-sanitised snapshot slug
        # that the derived-view writers consume (lifecycle/progress/views).
        "materialize",  # calls safe_mission_slug inside reduce()
        "reduce",  # safe_mission_slug applied at reduction boundary
    }
)

_SEAM_DISPOSITION = "routed-through-seam"
_TODO_DISPOSITION = "routed-through-seam (TODO)"
_FR009_FILE = "mission_metadata.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _names_in_file(path: Path) -> frozenset[str]:
    """Return all Name ids and Attribute.attr values referenced in *path*."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return frozenset(names)


def _load_inventory() -> list[dict[str, str]]:
    """Parse inventory.md and return the list of row dicts."""
    assert INVENTORY_PATH.exists(), (
        f"inventory.md missing at {INVENTORY_PATH} — "
        "the WP01 audit artifact must exist for WP04 to anchor on it."
    )
    text = INVENTORY_PATH.read_text(encoding="utf-8")
    rows = _parse_inventory_rows(text)
    assert rows, (
        "inventory.md parsed to zero rows — "
        "the file exists but the sink table is empty; "
        "this defeats the non-vacuous coverage assertion (T019-b)."
    )
    return rows


# ---------------------------------------------------------------------------
# T020: the WP01 audit must still pass on the current (fixed) tree
# ---------------------------------------------------------------------------


def test_audit_passes_on_fixed_tree() -> None:
    """The WP01 audit exits 0 on the WP02/WP03-fixed source tree (T020).

    Any undispositioned new join in an audited module surfaces here as a
    non-zero exit and a clear error message from audit.py.
    """
    exit_code = _audit_main()
    assert exit_code == 0, (
        "WP01 audit failed on the current source tree (see audit.py stderr for "
        "details).  This means either:\n"
        "  (a) a new untrusted-segment join was added to an audited module "
        "without updating inventory.md, or\n"
        "  (b) inventory.md is out of sync with the current source (line "
        "numbers shifted, rows removed, or a known-candidate file was deleted "
        "without updating KNOWN_CANDIDATE_FILES in audit.py).\n"
        "Fix: run `python -m tests.architectural.untrusted_path_audit.audit` "
        "to identify the specific failure, then update inventory.md."
    )


# ---------------------------------------------------------------------------
# T018 / T019-b: seam-presence + non-empty coverage assertion
# ---------------------------------------------------------------------------


def test_routed_through_seam_surfaces_still_reference_canonical_seam() -> None:
    """Each ``routed-through-seam`` surface still references a canonical seam (T018).

    Reads the WP01 inventory, extracts every module classified
    ``routed-through-seam`` (non-TODO), and asserts that the file's AST
    references at least one canonical seam name.

    A developer who removes the seam call while keeping the path join would:
      1. Still appear in ``discover_rows()`` (the join is still there), AND
      2. Fail this assertion (the seam name is gone from the AST).

    Non-empty coverage assertion (T019-b): the set of inspected surfaces
    must be non-empty and must equal the expected set from inventory — a
    vacuous guard that inspects zero files would pass all per-surface
    assertions trivially.
    """
    inventory_rows = _load_inventory()

    # Collect unique module paths for rows classified routed-through-seam (no TODO).
    seam_locators = [
        row["locator"]
        for row in inventory_rows
        if row["disposition"] == _SEAM_DISPOSITION
    ]
    assert seam_locators, (
        "inventory.md contains zero 'routed-through-seam' rows — "
        "either all surfaces were fixed (update this guard) or the inventory "
        "is empty/malformed (T019-b non-vacuous assertion)."
    )

    # Unique module paths (strip the :line suffix).
    expected_seam_surfaces: frozenset[str] = frozenset(
        loc.split(":")[0] for loc in seam_locators
    )

    # -----------------------------------------------------------------------
    # T019-b — coverage assertion: the set we inspect must match the inventory.
    # -----------------------------------------------------------------------
    assert len(expected_seam_surfaces) > 0, (
        "Expected seam-surface set is empty after parsing inventory rows — "
        "vacuous guard detected (T019-b)."
    )

    # Per-surface seam-presence check (T018).
    failures: list[str] = []
    inspected_surfaces: set[str] = set()

    for rel_path in sorted(expected_seam_surfaces):
        src_file = SRC_ROOT / rel_path
        assert src_file.exists(), (
            f"Audited surface {rel_path!r} no longer exists at {src_file} — "
            "update inventory.md and audited-surfaces.md to reflect the deletion."
        )

        file_names = _names_in_file(src_file)
        seam_refs = file_names & _SEAM_NAMES
        if not seam_refs:
            failures.append(
                f"{rel_path}: routed-through-seam per inventory but no canonical "
                f"seam name found in AST.  Expected at least one of: "
                f"{sorted(_SEAM_NAMES)}.  The seam call may have been removed "
                "while the path join (and the inventory row) remains — "
                "re-add the seam call or update the disposition to TODO."
            )

        inspected_surfaces.add(rel_path)

    # -----------------------------------------------------------------------
    # T019-b — guard the inspected set == expected set (no silent under-inspect).
    # -----------------------------------------------------------------------
    seam_surface_paths = frozenset(inspected_surfaces)
    assert seam_surface_paths == expected_seam_surfaces, (
        f"Inspected surface set differs from expected set.\n"
        f"  Expected : {sorted(expected_seam_surfaces)}\n"
        f"  Inspected: {sorted(seam_surface_paths)}\n"
        "This indicates a logic error in the guard itself."
    )

    assert not failures, (
        "One or more routed-through-seam surfaces no longer reference a "
        "canonical seam in their AST:\n"
        + "\n".join(f"  - {f}" for f in failures)
    )


# ---------------------------------------------------------------------------
# T018 (FR-009): inventory must contain the mission_metadata.py write-path row
# ---------------------------------------------------------------------------


def test_fr009_inventory_row_present() -> None:
    """The FR-009 mission_metadata.py write-path row is in inventory (T018/FR-009).

    ``audit.py`` check 4 enforces this at audit time; this test makes the
    assertion visible in the pytest run so CI surfaces it without running
    the audit script as a subprocess.
    """
    inventory_rows = _load_inventory()
    fr009_rows = [
        row
        for row in inventory_rows
        if row["locator"].startswith(_FR009_FILE)
    ]
    assert fr009_rows, (
        f"FR-009 candidate {_FR009_FILE!r} (meta.json write-path) is absent "
        "from inventory.md.  This row is an inventory-only assertion (RULESET §6) "
        "required by audit.py check 4."
    )
    dispositions = {row["disposition"] for row in fr009_rows}
    assert _TODO_DISPOSITION in dispositions or _SEAM_DISPOSITION in dispositions, (
        f"FR-009 {_FR009_FILE!r} row(s) must be tagged 'routed-through-seam (TODO)' "
        f"or 'routed-through-seam' (found: {sorted(dispositions)})."
    )


# ---------------------------------------------------------------------------
# T019-b supplement: discovered-row set is non-empty
# ---------------------------------------------------------------------------


def test_discovered_rows_non_empty() -> None:
    """The audit discovers at least one sink row (T019-b anti-vacuous guard).

    A guard that reports zero discovered rows would trivially pass T020
    (if the audit also vacuously passes).  This assertion ensures we are
    genuinely inspecting real source files.
    """
    rows = discover_rows()
    assert rows, (
        "audit.py discovered zero untrusted-segment → FS-sink rows across "
        "src/specify_cli.  This is almost certainly a SRC_ROOT misconfiguration "
        "or an empty source tree — not a genuine 'everything is safe' result."
    )


# ---------------------------------------------------------------------------
# T018 supplement: current discovered set is a subset of the inventory
# (no undispositioned rows — caught also by T020/audit_main, but explicit here)
# ---------------------------------------------------------------------------


def test_all_discovered_rows_appear_in_inventory() -> None:
    """Every AST-discovered sink row is present in inventory.md (T018/T020).

    This is the same check as ``audit.py`` check 2 (undercount), surfaced as a
    pytest assertion. It consumes the audit's OWN composite identity
    (``SinkRow.key()`` via :func:`build_discovered_key_map`) and its OWN pure
    seam (:func:`check_undercount`) — the raw ``f"{rel_path}:{line}"`` compare
    that used to live here (T008 / the #2306 fragility) is gone. There is now a
    single identity implementation shared by the audit and this guard.
    """
    inventory_rows = _load_inventory()
    parse_errors, inventory_keys = build_inventory_key_map(inventory_rows)
    assert not parse_errors, (
        "inventory.md has rows with an unparseable composite identity "
        "(missing qualname/token column):\n" + "\n".join(parse_errors)
    )

    discovered_keys = build_discovered_key_map(discover_rows())
    missing = check_undercount(discovered_keys, inventory_keys)

    assert not missing, (
        "The following untrusted-segment → FS-sink rows were discovered by the "
        "AST audit but are NOT in inventory.md (by composite identity):\n"
        + "\n".join(f"  {m}" for m in missing)
    )


# ---------------------------------------------------------------------------
# T011 — theater triad (drift / undercount / overcount) + the #2306 case.
#
# These drive the audit's REAL comparison seams (``check_undercount`` /
# ``check_overcount``) and identity (``composite_row_key`` / truncation) — the
# same functions ``audit.main()`` itself calls. Helper-only theater is a review
# reject, so two of the tests below invoke ``main()`` end-to-end with a
# monkeypatched discovery to prove the seams are wired into the real path.
# ---------------------------------------------------------------------------


def _key_from_source(rel_path: str, source: str, lineno: int) -> tuple[str, str, str]:
    """Composite row key from a source *string* — mirrors ``composite_row_key``.

    ``composite_row_key`` reads a file under ``SRC_ROOT``; this variant lets the
    theater build synthetic / shifted sources in memory while reusing the audit's
    exact identity (``composite_key`` + ``truncate_token``).
    """
    qualname, token = composite_key(source, lineno)
    return (rel_path, qualname, truncate_token(token))


def test_theater_line_only_drift_stays_green() -> None:
    """Leg (a): a documented sink whose line shifts +1 leaves the audit GREEN.

    Same qualname + token → same composite key despite the different line; both
    tripwire seams return no error.
    """
    src_before = "def f(mission_slug):\n    p = root / mission_slug\n"
    src_after = "def f(mission_slug):\n    # a freshly inserted comment\n    p = root / mission_slug\n"
    key_before = _key_from_source("m.py", src_before, 2)  # sink at line 2
    key_after = _key_from_source("m.py", src_after, 3)  # same sink, now line 3

    assert key_before == key_after, "line-only drift must NOT change composite identity"

    discovered = {key_after: "m.py:3"}  # live scan sees the shifted line
    inventory = {key_before: "m.py:2"}  # inventory frozen at the old locator
    assert check_undercount(discovered, inventory) == []
    assert check_overcount(discovered, inventory) == []


def test_theater_undocumented_sink_goes_red() -> None:
    """Leg (b): a discovered sink absent from the inventory trips undercount RED."""
    src = "def f(mission_slug):\n    p = root / mission_slug\n"
    key = _key_from_source("m.py", src, 2)

    errors = check_undercount({key: "m.py:2"}, {})
    assert errors, "an undocumented discovered sink must trip the undercount tripwire"
    assert "m.py:2" in errors[0]
    assert "undercount" in errors[0]


def test_theater_ghost_row_goes_red() -> None:
    """Leg (c): an inventory row with no live sink trips overcount/ghost RED."""
    src = "def f(mission_slug):\n    p = root / mission_slug\n"
    key = _key_from_source("m.py", src, 2)

    errors = check_overcount({}, {key: "m.py:5"})
    assert errors, "a ghost inventory row must trip the NEW overcount tripwire"
    assert "m.py:5" in errors[0]
    assert "overcount/ghost" in errors[0]


def test_2306_documented_sink_shifted_one_line_stays_green() -> None:
    """The #2306 case by name: a documented sink shifted exactly one line is GREEN.

    #2306 reddened CI when the ``_mt_warn_worktree_kitty_specs`` probe in
    ``tasks_move_task.py`` shifted a single line under the old raw ``rel:line``
    compare. Reproduce that exact historical shape against the LIVE sink and
    assert the composite identity keeps it green.
    """
    rel = "cli/commands/agent/tasks_move_task.py"
    src = (SRC_ROOT / rel).read_text(encoding="utf-8")
    lines = src.splitlines(keepends=True)

    sink_idx = next(
        i for i, line in enumerate(lines) if "worktree_kitty / st.mission_slug" in line
    )
    sink_lineno = sink_idx + 1  # 1-based
    key_before = _key_from_source(rel, src, sink_lineno)

    # #2306 shape: insert one blank line above the sink (the off-by-one shift).
    shifted_src = "".join(lines[:sink_idx] + ["\n"] + lines[sink_idx:])
    key_after = _key_from_source(rel, shifted_src, sink_lineno + 1)

    assert key_before == key_after, (
        "#2306 regression: a one-line shift of _mt_warn_worktree_kitty_specs must "
        "NOT change the composite identity"
    )

    discovered = {key_after: f"{rel}:{sink_lineno + 1}"}
    inventory = {key_before: f"{rel}:{sink_lineno}"}
    assert check_undercount(discovered, inventory) == []
    assert check_overcount(discovered, inventory) == []


def test_main_flags_injected_undocumented_sink(monkeypatch: pytest.MonkeyPatch) -> None:
    """``main()`` returns non-zero when a NEW undocumented sink is discovered.

    Drives the REAL ``main()`` path (not a helper): monkeypatch discovery to add
    a synthetic sink whose composite key is absent from inventory.md → the
    undercount seam ``main()`` calls trips and ``main()`` exits 1.
    """
    from tests.architectural.untrusted_path_audit import audit as audit_mod

    real_discover = audit_mod.discover_rows

    def _fake() -> list[audit_mod.SinkRow]:
        rows = list(real_discover())
        # A real source line (mission_metadata.py:30) whose composite key is not
        # documented in inventory.md — a genuine new offending site.
        rows.append(audit_mod.SinkRow("mission_metadata.py", 30, "mission_slug", "Path-join (/)"))
        return rows

    monkeypatch.setattr(audit_mod, "discover_rows", _fake)
    assert audit_mod.main() == 1


def test_main_flags_ghost_when_discovered_sink_disappears(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``main()`` returns non-zero when a documented sink vanishes (overcount).

    Drives the REAL ``main()`` path: monkeypatch discovery to drop a live
    non-tagged sink → its inventory row becomes a ghost → the overcount seam
    ``main()`` calls trips and ``main()`` exits 1.
    """
    from tests.architectural.untrusted_path_audit import audit as audit_mod

    real_discover = audit_mod.discover_rows

    def _fake() -> list[audit_mod.SinkRow]:
        # Drop the audit/engine.py sink (a discovered, non-inventory-only row).
        return [r for r in real_discover() if r.rel_path != "audit/engine.py"]

    monkeypatch.setattr(audit_mod, "discover_rows", _fake)
    assert audit_mod.main() == 1


def test_inventory_only_rows_carry_a_documented_reason() -> None:
    """Every ``[inventory-only]`` row names WHY it is exempt from overcount.

    The tag is the ONLY overcount escape hatch; an untagged reason (a bare tag)
    would let a genuinely-deleted sink hide. Each tagged row must carry prose
    beyond the tag itself.
    """
    inventory_rows = _load_inventory()
    tagged = [r for r in inventory_rows if INVENTORY_ONLY_TAG in r["rationale"]]
    assert tagged, "expected the known-false-negative rows to carry the tag"
    for row in tagged:
        remainder = row["rationale"].replace(INVENTORY_ONLY_TAG, "").strip()
        assert len(remainder) > 20, (
            f"[inventory-only] row {row['locator']!r} must document WHY it is "
            "exempt (removed-sink change or known-FN class), not just the bare tag."
        )


# ---------------------------------------------------------------------------
# #6642 — pure sink relocation: pairing, --fix, and the teeth that stay.
#
# A change that only MOVES a sink (module renamed / function relocated, joined
# segment unchanged) used to report two failures — a ghost overcount plus an
# undercount — forcing a hand re-pin of the inventory locator columns. The
# audit now pairs a pure move: one ghost row + one missing live sink uniquely
# sharing (token, untrusted source) collapse into ONE "sink moved" finding,
# and ``--fix`` re-pins only the machine locator columns (file:line, qualname).
# Every other tripwire keeps its exact strictness (teeth tests below).
# ---------------------------------------------------------------------------

from tests.architectural._ratchet_keys import composite_key_from_file  # noqa: E402
from typing import cast  # noqa: E402
from tests.architectural.untrusted_path_audit.audit import pair_relocations  # noqa: E402
from tests.architectural.untrusted_path_audit.audit import RelocationPair  # noqa: E402
from tests.architectural.untrusted_path_audit.audit import SinkRow  # noqa: E402


def _synth_key(rel: str, qualname: str, token: str) -> tuple[str, str, str]:
    """A synthetic composite key — pair_relocations only compares strings."""
    return (rel, qualname, token)


# --- Unit level: the pairing seam (pure, no file access) -------------------


def test_pure_move_pairs_into_single_relocation() -> None:
    """One ghost + one missing sink sharing (token, source) pair uniquely."""
    ghost = _synth_key("old/mod.py", "f", "p = root / mission_slug")
    moved = _synth_key("new/mod.py", "f", "p = root / mission_slug")
    discovered = {moved: ("new/mod.py:9", "mission_slug")}
    inventory = {ghost: ("old/mod.py:4", "mission_slug")}
    pairs, notes = pair_relocations(discovered, inventory)
    assert pairs == [RelocationPair(ghost, "old/mod.py:4", moved, "new/mod.py:9")]
    assert notes == []


def test_pure_move_with_qualname_change_pairs() -> None:
    """A function relocated into another function pairs (qualname changed)."""
    ghost = _synth_key("mod.py", "outer", "p = root / mission_slug")
    moved = _synth_key("mod.py", "Outer.inner", "p = root / mission_slug")
    pairs, _ = pair_relocations(
        {moved: ("mod.py:12", "mission_slug")}, {ghost: ("mod.py:4", "mission_slug")}
    )
    assert len(pairs) == 1 and pairs[0].ghost_key == ghost and pairs[0].missing_key == moved


def test_genuine_removal_never_pairs() -> None:
    """Teeth: a removed sink (ghost, no missing twin) never pairs."""
    ghost = _synth_key("old/mod.py", "f", "p = root / mission_slug")
    pairs, notes = pair_relocations({}, {ghost: ("old/mod.py:4", "mission_slug")})
    assert pairs == [] and notes == []


def test_genuine_new_sink_never_pairs() -> None:
    """Teeth: a new sink (missing, no ghost twin) never pairs."""
    moved = _synth_key("new/mod.py", "f", "p = root / mission_slug")
    pairs, notes = pair_relocations({moved: ("new/mod.py:9", "mission_slug")}, {})
    assert pairs == [] and notes == []


def test_token_changed_move_never_pairs() -> None:
    """Teeth: a relocation whose joined segment changed breaks the pair key."""
    ghost = _synth_key("old/mod.py", "f", "p = root / mission_slug")
    changed = _synth_key("new/mod.py", "f", "p = root / mission_slug . name")
    pairs, notes = pair_relocations(
        {changed: ("new/mod.py:9", "mission_slug")}, {ghost: ("old/mod.py:4", "mission_slug")}
    )
    assert pairs == []
    # No note either: the tokens do not match, so there is nothing to explain.
    assert notes == []


def test_source_mismatch_never_pairs_and_notes() -> None:
    """Teeth: same token, different untrusted source cells — no pairing, a note."""
    ghost = _synth_key("old/mod.py", "f", "p = root / mission_slug")
    moved = _synth_key("new/mod.py", "f", "p = root / mission_slug")
    pairs, notes = pair_relocations(
        {moved: ("new/mod.py:9", "mission_slug")}, {ghost: ("old/mod.py:4", "slug")}
    )
    assert pairs == []
    assert len(notes) == 1
    assert "source differs" in notes[0]


def test_truncated_token_never_auto_pairs() -> None:
    """Teeth: a …-truncated token never auto-pairs (prefix collisions)."""
    ghost = _synth_key("old/mod.py", "f", "p = root / a / mission_slug / b / c / d…")
    moved = _synth_key("new/mod.py", "f", "p = root / a / mission_slug / b / c / d…")
    pairs, notes = pair_relocations(
        {moved: ("new/mod.py:9", "mission_slug")}, {ghost: ("old/mod.py:4", "mission_slug")}
    )
    assert pairs == []
    assert len(notes) == 1
    assert "truncated" in notes[0]


def test_ambiguous_two_ghosts_one_missing_never_pairs() -> None:
    """Teeth: 2 ghosts vs 1 missing in one (token, source) group is ambiguous."""
    g1 = _synth_key("a/mod.py", "f", "p = root / mission_slug")
    g2 = _synth_key("b/mod.py", "f", "p = root / mission_slug")
    moved = _synth_key("c/mod.py", "f", "p = root / mission_slug")
    pairs, notes = pair_relocations(
        {moved: ("c/mod.py:9", "mission_slug")},
        {g1: ("a/mod.py:4", "mission_slug"), g2: ("b/mod.py:4", "mission_slug")},
    )
    assert pairs == []
    assert any("ambiguous" in n for n in notes)


def test_ambiguous_one_ghost_two_missing_never_pairs() -> None:
    """Teeth: 1 ghost vs 2 missing in one (token, source) group is ambiguous."""
    ghost = _synth_key("a/mod.py", "f", "p = root / mission_slug")
    m1 = _synth_key("b/mod.py", "f", "p = root / mission_slug")
    m2 = _synth_key("c/mod.py", "f", "p = root / mission_slug")
    pairs, notes = pair_relocations(
        {m1: ("b/mod.py:4", "mission_slug"), m2: ("c/mod.py:9", "mission_slug")},
        {ghost: ("a/mod.py:4", "mission_slug")},
    )
    assert pairs == []
    assert any("ambiguous" in n for n in notes)


def test_two_ghosts_zero_missing_never_pairs() -> None:
    """Teeth: two ghosts sharing (token, source) with no missing sink stay red."""
    g1 = _synth_key("a/mod.py", "f", "p = root / mission_slug")
    g2 = _synth_key("b/mod.py", "f", "p = root / mission_slug")
    pairs, notes = pair_relocations(
        {}, {g1: ("a/mod.py:4", "mission_slug"), g2: ("b/mod.py:4", "mission_slug")}
    )
    assert pairs == []


def test_multiple_distinct_relocations_pair_independently() -> None:
    """Two unique (token, source) groups pair independently in one run."""
    g1 = _synth_key("a/mod.py", "f", "p = root / mission_slug")
    m1 = _synth_key("x/mod.py", "f", "p = root / mission_slug")
    g2 = _synth_key("b/mod.py", "g", "q = base / wp_slug")
    m2 = _synth_key("y/mod.py", "g", "q = base / wp_slug")
    pairs, notes = pair_relocations(
        {m1: ("x/mod.py:1", "mission_slug"), m2: ("y/mod.py:2", "wp_slug")},
        {g1: ("a/mod.py:1", "mission_slug"), g2: ("b/mod.py:2", "wp_slug")},
    )
    assert len(pairs) == 2 and notes == []
    assert {p.ghost_key for p in pairs} == {g1, g2}
    assert {p.missing_key for p in pairs} == {m1, m2}


# --- End-to-end level: main() reports the single finding -------------------


def _relocate_cycle_sink(monkeypatch: pytest.MonkeyPatch, new_rel: str) -> None:
    """Simulate a pure module rename of the live ``review/cycle.py:52`` sink.

    The row inventoried at ``review/cycle.py:52`` (live line 278,
    ``_review_cycle_wp_dir``) moves VERBATIM to ``new_rel``: same content, same
    line, same token/qualname — only the module path changes. This patches the
    identity helper's file lookup (the moved module has identical content) and
    discovery's row set, the same seams ``main()`` itself consumes.
    """
    from tests.architectural.untrusted_path_audit import audit as audit_mod

    real_discover = audit_mod.discover_rows
    real_ckff = composite_key_from_file

    def _redirect_ckff(path: Path, line: int) -> tuple[str, str]:
        try:
            rel = path.relative_to(audit_mod.SRC_ROOT).as_posix()
        except ValueError:
            return cast(tuple[str, str], real_ckff(path, line))
        if rel == new_rel:
            path = audit_mod.SRC_ROOT / "review/cycle.py"
        return cast(tuple[str, str], real_ckff(path, line))

    def _fake_discover() -> list[SinkRow]:
        rows: list[SinkRow] = []
        for row in real_discover():
            if row.rel_path == "review/cycle.py" and row.line == 278:
                rows.append(
                    audit_mod.SinkRow(new_rel, row.line, row.untrusted_source, row.sink_op)
                )
            else:
                rows.append(row)
        return rows

    monkeypatch.setattr(audit_mod, "composite_key_from_file", _redirect_ckff)
    monkeypatch.setattr(audit_mod, "discover_rows", _fake_discover)


def test_main_reports_pure_relocation_as_single_moved_finding(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """#6642 red-first core: a pure move yields ONE finding, not two errors."""
    from tests.architectural.untrusted_path_audit import audit as audit_mod

    _relocate_cycle_sink(monkeypatch, "review/cycle_relocated.py")
    assert audit_mod.main() == 1  # still red until the inventory is re-pinned
    err = capsys.readouterr().err
    assert err.count("sink moved:") == 1
    assert "review/cycle.py" in err and "review/cycle_relocated.py" in err
    # The two misleading failures are gone for this sink.
    assert "overcount/ghost" not in err
    assert "undercount" not in err
    assert "--fix" in err  # the finding tells the contributor how to re-pin


def test_main_green_tree_output_has_no_relocation_noise(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """NFR-001: on the green tree the audit output stays a plain summary."""
    from tests.architectural.untrusted_path_audit import audit as audit_mod

    assert audit_mod.main() == 0
    out = capsys.readouterr()
    assert out.err == ""
    assert out.out.startswith("AUDIT OK:")
    assert "sink moved" not in out.out


# --- End-to-end level: --fix re-pins exactly the locator columns ----------


def _tmp_inventory_copy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point the audit at a scratch copy of the real inventory."""
    from tests.architectural.untrusted_path_audit import audit as audit_mod

    scratch = tmp_path / "inventory.md"
    scratch.write_text(audit_mod.INVENTORY_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(audit_mod, "INVENTORY_PATH", scratch)
    return scratch


def test_fix_repins_relocated_row_and_goes_green(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """--fix re-pins the locator columns; disposition/rationale untouched."""
    from tests.architectural.untrusted_path_audit import audit as audit_mod

    scratch = _tmp_inventory_copy(monkeypatch, tmp_path)
    before = (scratch.read_text(encoding="utf-8")).splitlines()
    ghost_line = next(
        ln for ln in before if ln.startswith("| review/cycle.py:52 | _review_cycle_wp_dir |")
    )
    ghost_cells = [c.strip() for c in ghost_line.strip("|").split("|")]

    _relocate_cycle_sink(monkeypatch, "review/cycle_relocated.py")
    assert audit_mod.main(["--fix"]) == 0
    out = capsys.readouterr()
    assert "AUDIT FIXED: re-pinned 1 relocated sink row" in out.out

    after = (scratch.read_text(encoding="utf-8")).splitlines()
    fixed_line = next(
        ln for ln in after if ln.startswith("| review/cycle_relocated.py:278 | _review_cycle_wp_dir |")
    )
    fixed_cells = [c.strip() for c in fixed_line.strip("|").split("|")]
    # Locator columns re-pinned (file:line + qualname).
    assert fixed_cells[0] == "review/cycle_relocated.py:278"
    assert fixed_cells[1] == ghost_cells[1]
    # Token, source, sink op, disposition, rationale: byte-identical.
    assert fixed_cells[2:] == ghost_cells[2:]

    # The fixed tree is green for a plain run, and --fix is now a no-op.
    assert audit_mod.main() == 0
    assert audit_mod.main(["--fix"]) == 0
    assert scratch.read_text(encoding="utf-8") == "\n".join(after) + "\n"


def test_fix_without_relocations_writes_nothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """--fix on a green tree is a no-op (no write, plain summary)."""
    from tests.architectural.untrusted_path_audit import audit as audit_mod

    scratch = _tmp_inventory_copy(monkeypatch, tmp_path)
    before = scratch.read_text(encoding="utf-8")
    assert audit_mod.main(["--fix"]) == 0
    out = capsys.readouterr()
    assert "AUDIT FIXED" not in out.out
    assert out.out.startswith("AUDIT OK:")
    assert scratch.read_text(encoding="utf-8") == before


def test_fix_fail_closed_on_unrelated_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Teeth: --fix refuses to write while any non-relocation error exists."""
    from tests.architectural.untrusted_path_audit import audit as audit_mod

    scratch = _tmp_inventory_copy(monkeypatch, tmp_path)
    # Corrupt one unrelated row's disposition (an error --fix cannot resolve).
    lines = scratch.read_text(encoding="utf-8").splitlines()
    i = next(n for n, ln in enumerate(lines) if ln.startswith("| audit/engine.py:88 |"))
    lines[i] = lines[i].replace("| unreachable |", "| bogus-disposition |")
    assert lines[i] != scratch.read_text(encoding="utf-8").splitlines()[i]
    corrupted = "\n".join(lines) + "\n"
    scratch.write_text(corrupted, encoding="utf-8")

    _relocate_cycle_sink(monkeypatch, "review/cycle_relocated.py")
    assert audit_mod.main(["--fix"]) == 1
    # Fail-closed: the scratch file is byte-identical (no partial write).
    assert scratch.read_text(encoding="utf-8") == corrupted


def test_fix_refuses_when_repinned_tree_would_still_fail(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Teeth: --fix re-audits the would-be result in memory before writing.

    Defense-in-depth for a buggy rewrite: if the re-pinned inventory would
    still fail any check, --fix reports it and leaves the file untouched.
    """
    from tests.architectural.untrusted_path_audit import audit as audit_mod

    scratch = _tmp_inventory_copy(monkeypatch, tmp_path)
    before = scratch.read_text(encoding="utf-8")

    real_apply = audit_mod._apply_relocation_fixes

    def _buggy_apply(text: str, pairs: list[RelocationPair]) -> str:
        # A (hypothetically) broken rewrite: re-pins the relocation AND
        # corrupts one unrelated disposition.
        return real_apply(text, pairs).replace(
            "| unreachable |", "| bogus-disposition |", 1
        )

    monkeypatch.setattr(audit_mod, "_apply_relocation_fixes", _buggy_apply)

    _relocate_cycle_sink(monkeypatch, "review/cycle_relocated.py")
    rc = audit_mod.main(["--fix"])
    assert rc == 1
    # Refused: the scratch inventory is byte-identical (no partial write).
    assert scratch.read_text(encoding="utf-8") == before


def test_fix_repins_two_independent_relocations(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Two distinct pure moves in one run: both re-pinned, one --fix pass."""
    from tests.architectural.untrusted_path_audit import audit as audit_mod

    scratch = _tmp_inventory_copy(monkeypatch, tmp_path)

    real_discover = audit_mod.discover_rows
    real_ckff = composite_key_from_file

    def _redirect_ckff(path: Path, line: int) -> tuple[str, str]:
        try:
            rel = path.relative_to(audit_mod.SRC_ROOT).as_posix()
        except ValueError:
            return cast(tuple[str, str], real_ckff(path, line))
        if rel in ("review/moved_a.py", "review/moved_b.py"):
            path = audit_mod.SRC_ROOT / "review/cycle.py"
        return cast(tuple[str, str], real_ckff(path, line))

    def _fake_discover() -> list[SinkRow]:
        rows: list[SinkRow] = []
        for row in real_discover():
            if row.rel_path == "review/cycle.py" and row.line == 278:
                rows.append(audit_mod.SinkRow("review/moved_a.py", row.line, row.untrusted_source, row.sink_op))
            elif row.rel_path == "review/cycle.py" and row.line == 294:
                rows.append(audit_mod.SinkRow("review/moved_b.py", row.line, row.untrusted_source, row.sink_op))
            else:
                rows.append(row)
        return rows

    monkeypatch.setattr(audit_mod, "composite_key_from_file", _redirect_ckff)
    monkeypatch.setattr(audit_mod, "discover_rows", _fake_discover)

    assert audit_mod.main() == 1  # red: two "sink moved" findings
    assert capsys.readouterr().err.count("sink moved:") == 2

    assert audit_mod.main(["--fix"]) == 0
    assert "re-pinned 2 relocated sink row" in capsys.readouterr().out
    fixed = scratch.read_text(encoding="utf-8")
    assert "| review/moved_a.py:278 | _review_cycle_wp_dir |" in fixed
    assert "| review/moved_b.py:294 |" in fixed
    assert audit_mod.main() == 0


# --- The two hygiene guards are pinned in BOTH directions (#6642 review B-1):
# --- a red-direction test per guard (the check FIRES on a corrupted inventory)
# --- plus green-tree assertions that they hold on the committed inventory.
# --- Removing either check from _collect_errors, or weakening the chain regex,
# --- turns these red.


def test_main_flags_hand_tuned_source_cell(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Check 5 fires: a non-canonical source cell on a LIVE row is RED."""
    from tests.architectural.untrusted_path_audit import audit as audit_mod

    scratch = _tmp_inventory_copy(monkeypatch, tmp_path)
    lines = scratch.read_text(encoding="utf-8").splitlines()
    i = next(n for n, ln in enumerate(lines) if ln.startswith("| audit/engine.py:88 |"))
    # Hand-tune the source cell back to the receiver-qualified form (the exact
    # pre-#6642 state of this row): pairing would silently miss it.
    lines[i] = lines[i].replace("| mission_slug | Path-join", "| resolved.mission_slug | Path-join", 1)
    assert "resolved.mission_slug" in lines[i]
    scratch.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert audit_mod.main() == 1
    # Not committed above: read the error off stderr via a fresh run.
    import contextlib
    import io

    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        assert audit_mod.main() == 1
    assert "audit/engine.py:88" in err.getvalue()
    assert "not the canonical machine string 'mission_slug'" in err.getvalue()


def test_main_flags_line_shift_chain_arrow_form(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Check 6 fires on the ``1902→1933`` arrow form (SC-004's letter)."""
    from tests.architectural.untrusted_path_audit import audit as audit_mod

    scratch = _tmp_inventory_copy(monkeypatch, tmp_path)
    lines = scratch.read_text(encoding="utf-8").splitlines()
    i = next(n for n, ln in enumerate(lines) if ln.startswith("| audit/engine.py:88 |"))
    lines[i] = lines[i].replace(
        "Path-join (/) | unreachable |",
        "Path-join (/) | unreachable | (line shifted 88→107 by a hypothetical mission.)",
        1,
    )
    scratch.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert audit_mod.main() == 1


def test_main_flags_line_shift_chain_prose_form(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Check 6 fires on the signed-shift prose form (``shifted −11``)."""
    from tests.architectural.untrusted_path_audit import audit as audit_mod

    scratch = _tmp_inventory_copy(monkeypatch, tmp_path)
    lines = scratch.read_text(encoding="utf-8").splitlines()
    i = next(n for n, ln in enumerate(lines) if ln.startswith("| audit/engine.py:88 |"))
    lines[i] = lines[i].replace(
        "Path-join (/) | unreachable |",
        "Path-join (/) | unreachable | (shifted −11 by a rebase.)",
        1,
    )
    scratch.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert audit_mod.main() == 1


def test_chain_guard_regex_covers_both_forms_and_clean_prose() -> None:
    """The regex itself: both shift forms match; ordinary prose does not."""
    from tests.architectural.untrusted_path_audit.audit import _LINE_SHIFT_CHAIN_RE

    assert _LINE_SHIFT_CHAIN_RE.search("line shifted 1902→1933 by mission X")
    assert _LINE_SHIFT_CHAIN_RE.search("relocated; shifted −11 by a rebase")
    assert _LINE_SHIFT_CHAIN_RE.search("shifted +2 by mission Y")
    assert _LINE_SHIFT_CHAIN_RE.search("then 518→472 by deletion")
    assert _LINE_SHIFT_CHAIN_RE.search("relocated VERBATIM from merge.py:613") is None
    assert _LINE_SHIFT_CHAIN_RE.search("disposition unchanged; same sink") is None


def test_committed_inventory_has_no_line_shift_chains() -> None:
    """SC-004 green direction: no committed rationale carries a shift chain."""
    from tests.architectural.untrusted_path_audit import audit as audit_mod

    rows = audit_mod._parse_inventory_rows(
        audit_mod.INVENTORY_PATH.read_text(encoding="utf-8")
    )
    assert rows, "sink table must parse"
    assert audit_mod._check_no_line_shift_chains(rows) == []


def test_committed_inventory_source_cells_are_canonical() -> None:
    """Check 5 green direction: every live row's source cell is machine-canonical."""
    from tests.architectural.untrusted_path_audit import audit as audit_mod

    discovered = audit_mod._build_rich_discovered(audit_mod.discover_rows())
    rows = audit_mod._parse_inventory_rows(
        audit_mod.INVENTORY_PATH.read_text(encoding="utf-8")
    )
    assert audit_mod._check_source_canonicality(discovered, rows) == []
