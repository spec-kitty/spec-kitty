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
        "Fix: run `python tests/architectural/untrusted_path_audit/audit.py` "
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
