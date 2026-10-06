"""WP02 (mission runtime-advance-guard-topology-wp-completion-01M1W6VZ, issue
#3884): coord-topology test fixture + FR-009-isolated reachability
reproduction (test-only -- no `src/` change; see `tasks/WP02-coord-topology-
fixture-repro1.md`).

Exports :func:`build_coord_topology_fixture` (and :class:`CoordTopologyFixture`,
T001) as the reusable fixture builder WP01's own reproductions
(``test_advance_guard_coord_reachability.py``) import directly -- a plain
dotted cross-test-module import (``from tests.runtime.next.
test_coord_topology_fixture import build_coord_topology_fixture``), verified
against this repo's own precedent before assuming it would work
(``tests/agent/test_finalize_tasks_owned_files_validation.py`` already imports
from ``tests.tasks.test_finalize_tasks_owned_files_validation`` the same way,
despite ``tests/runtime/next/`` carrying no ``__init__.py`` -- Python's
implicit-namespace-package resolution absorbs the gap under both a plain
interpreter import and pytest's own collection, confirmed empirically for
this exact path during T005). No ``conftest.py`` addition was needed (Risks
section in the tasks file).

**T002 empirical finding (dated 2026-09-07, see tracer-design-decisions.md for
the full dated entry):** CONFIRMED -- ``feature_dir.name`` for a real
coord-topology mission's coordination-worktree directory (the composed
``<slug>-<mid8>`` form ``coord_feature_dir`` actually produces on disk) round-
trips through ``mission_runtime.placement_seam(repo_root, feature_dir.name)
.read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)`` to the IDENTICAL primary
directory the bare ``mission_slug`` resolves to. FR-009's ``mission_slug``
fallback (``mission_slug if mission_slug is not None else feature_dir.name``)
is therefore safe for both forms; no reproduction needs to pass
``mission_slug`` explicitly to route around a fallback failure.

T004 pairs T003 with a regression pin: the SAME event content, read directly
from `primary_dir` (no coord split), already correctly blocks today --
proving T003's RED is specifically the coord-anchoring gap.

The fixture builds a REAL coord-topology mission split -- an actual git repo,
a real coordination branch, and the coordination-worktree directory shape
``specify_cli.missions._read_path_resolver.coord_feature_dir`` composes --
never a mocked or monkeypatched stand-in. This mirrors (independently
verified as a real precedent, not merely assumed) the un-stubbed construction
style already established by ``tests/integration/coord_topology_fixture.py``
("No resolver is patched anywhere in this module. All topology routing uses
real git + filesystem state"), though that module solves a different problem
(identity-divergence decoys/sentinels for a different mission) and is not
reused here: this WP's own contract calls for a `wp_events`-parameterized
builder isolating an `in_progress` claim, a shape that module does not offer.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from mission_runtime import MissionArtifactKind, placement_seam
from runtime.next.runtime_bridge_guards import _should_advance_wp_step, _wp_blocks_step
from specify_cli.missions._read_path_resolver import (
    coord_feature_dir as _compose_coord_feature_dir,
)
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event
from specify_cli.status.wp_state import wp_state_for

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

# Real-shaped identity (a genuine 26-char Crockford ULID + its 8-char mid8
# prefix), mirroring the precedent in tests/mission_runtime/test_placement_seam.py.
_FIXTURE_MISSION_ID = "01KWZ46V5P3QY7M8N0RAB4CDEF"
_FIXTURE_MID8 = _FIXTURE_MISSION_ID[:8]
_DEFAULT_WP_ID = "WP01"
_MISSION_SLUG = "coord-topology-fixture-wp02"


@dataclass(frozen=True)
class CoordTopologyFixture:
    """Paths for one built coord-topology fixture (T001).

    ``primary_dir`` and ``coord_feature_dir`` genuinely diverge on disk: only
    ``primary_dir`` carries ``tasks/`` (a PRIMARY-partition artifact,
    ``MissionArtifactKind.WORK_PACKAGE_TASK`` -- never received by a
    coordination worktree, per spec.md's Scope Narrowing / plan.md's FR-009
    section), and only ``coord_feature_dir`` is the coordination-worktree
    shape a real coord-topology mission's runtime advance-guard call actually
    receives as its ``feature_dir`` argument.
    """

    primary_dir: Path
    coord_feature_dir: Path
    repo_root: Path
    mission_slug: str


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo_root, check=True, capture_output=True)


def claim_and_start_events(wp_id: str = _DEFAULT_WP_ID) -> list[dict[str, Any]]:
    """Return the claim + ``in_progress`` transition pair T003/T004 seed.

    A lane that ALREADY correctly blocks under today's un-patched
    ``_wp_blocks_step`` (``is_run_affecting=True``, not in
    ``{FOR_REVIEW, APPROVED}``) -- deliberately NOT an uninitialized WP, so a
    reproduction built on this event pair can isolate FR-009's coord-anchoring
    bug from FR-004's separate ``Lane.UNINITIALIZED`` gap (see the WP02 tasks
    file's Context section for the full isolation rationale).
    """
    return [
        {"wp_id": wp_id, "from_lane": Lane.PLANNED, "to_lane": Lane.CLAIMED},
        {"wp_id": wp_id, "from_lane": Lane.CLAIMED, "to_lane": Lane.IN_PROGRESS},
    ]


def _write_events(feature_dir: Path, mission_slug: str, wp_events: list[dict[str, Any]] | None) -> None:
    """Write *wp_events* to ``feature_dir``'s ``status.events.jsonl`` via the
    real ``specify_cli.status.store.append_event`` I/O path (never hand-
    crafted JSON) -- an empty (zero-line) file when *wp_events* is falsy,
    which folds to ``Lane.UNINITIALIZED`` on read (WP01's own default-variant
    reuse case, tasks file T001 step 3)."""
    events_path = feature_dir / "status.events.jsonl"
    events_path.touch()
    for index, spec in enumerate(wp_events or []):
        append_event(
            feature_dir,
            StatusEvent(
                event_id=f"wp02-fixture-{index:03d}",
                mission_slug=mission_slug,
                wp_id=spec.get("wp_id", _DEFAULT_WP_ID),
                from_lane=Lane(spec["from_lane"]),
                to_lane=Lane(spec["to_lane"]),
                at="2026-01-01T00:00:00+00:00",
                actor="wp02-fixture",
                force=True,
                execution_mode="worktree",
            ),
        )


def build_coord_topology_fixture(tmp_path: Path, *, wp_events: list[dict[str, Any]] | None = None) -> CoordTopologyFixture:
    """Build a REAL coord-topology mission fixture (T001).

    Materializes: a real git repo (``.kittify/config.yaml`` present, so
    ``mission_runtime.placement_seam`` resolution has a genuine repo root to
    anchor on); a ``primary_dir`` (``<repo>/kitty-specs/<slug>/``) carrying a
    real ``meta.json`` (``topology: coord``) and a real ``tasks/WP01-
    sample.md``; a real coordination branch; and a ``coord_feature_dir`` --
    the EXACT directory ``specify_cli.missions._read_path_resolver.
    coord_feature_dir`` composes for that branch -- holding ONLY
    ``status.events.jsonl`` seeded with *wp_events* (never ``tasks/``, never
    ``meta.json``: the coordination worktree genuinely never receives the
    PRIMARY-partition artifacts a coord-topology mission's coordination
    branch is cut before ``specify``/``plan``/``tasks`` ever run, per spec.md's
    Scope Narrowing section).

    The SAME *wp_events* are also written to ``primary_dir``'s own
    ``status.events.jsonl`` (T004's regression-pin surface): this is the
    realistic shape a flattened/``single_branch`` mission's feature_dir
    genuinely has (``tasks/`` and ``status.events.jsonl`` co-located), which
    is exactly what makes the T004 pin a genuine parallel comparison rather
    than an artificial one.

    ``wp_events`` defaults to ``None`` (zero events, folds to
    ``Lane.UNINITIALIZED``) so WP01 can reuse this default for its own
    uninitialized-WP reproduction without re-specifying it.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.email", "wp02-fixture@spec-kitty.test")
    _git(repo_root, "config", "user.name", "WP02 Fixture")
    _git(repo_root, "config", "commit.gpgsign", "false")
    (repo_root / ".kittify").mkdir()
    (repo_root / ".kittify" / "config.yaml").write_text("agents:\n  available:\n    - claude\n", encoding="utf-8")

    coord_branch = f"kitty/mission-{_MISSION_SLUG}-{_FIXTURE_MID8}"
    meta: dict[str, object] = {
        "mission_id": _FIXTURE_MISSION_ID,
        "mission_slug": _MISSION_SLUG,
        "mission_type": "software-dev",
        "target_branch": "fix/runtime-advance-guard-3883",
        "friendly_name": "WP02 coord-topology fixture",
        "topology": "coord",
        "coordination_branch": coord_branch,
    }

    primary_dir = repo_root / "kitty-specs" / _MISSION_SLUG
    primary_dir.mkdir(parents=True)
    (primary_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    tasks_dir = primary_dir / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / f"{_DEFAULT_WP_ID}-sample.md").write_text(
        f"---\nwork_package_id: {_DEFAULT_WP_ID}\ntitle: WP02 fixture sample\n---\n# {_DEFAULT_WP_ID}\nFixture-only placeholder; content is not read.\n",
        encoding="utf-8",
    )
    _git(repo_root, "add", ".")
    _git(repo_root, "commit", "-q", "-m", "WP02 fixture: primary checkout")

    _git(repo_root, "branch", coord_branch)
    coord_dir = _compose_coord_feature_dir(repo_root, _MISSION_SLUG, _FIXTURE_MID8)
    coord_dir.mkdir(parents=True)

    _write_events(coord_dir, _MISSION_SLUG, wp_events)
    _write_events(primary_dir, _MISSION_SLUG, wp_events)

    return CoordTopologyFixture(
        primary_dir=primary_dir,
        coord_feature_dir=coord_dir,
        repo_root=repo_root,
        mission_slug=_MISSION_SLUG,
    )


# ---------------------------------------------------------------------------
# T001 -- fixture builder standalone validation
# ---------------------------------------------------------------------------


class TestT001FixtureBuilder:
    def test_coord_side_never_receives_tasks_and_carries_only_the_events_file(self, tmp_path: Path) -> None:
        fixture = build_coord_topology_fixture(tmp_path, wp_events=claim_and_start_events())

        assert not (fixture.coord_feature_dir / "tasks").exists()
        assert not (fixture.coord_feature_dir / "meta.json").exists()
        coord_contents = sorted(p.name for p in fixture.coord_feature_dir.iterdir())
        assert coord_contents == ["status.events.jsonl"]

    def test_primary_side_carries_the_real_wp_task_file(self, tmp_path: Path) -> None:
        fixture = build_coord_topology_fixture(tmp_path, wp_events=claim_and_start_events())

        wp_file = fixture.primary_dir / "tasks" / f"{_DEFAULT_WP_ID}-sample.md"
        assert wp_file.is_file()
        assert wp_file.read_text(encoding="utf-8").strip() != ""

    def test_wp_events_content_matches_what_was_supplied(self, tmp_path: Path) -> None:
        fixture = build_coord_topology_fixture(tmp_path, wp_events=claim_and_start_events())

        raw_lines = (fixture.coord_feature_dir / "status.events.jsonl").read_text(encoding="utf-8").splitlines()
        transitions = [(json.loads(line)["from_lane"], json.loads(line)["to_lane"]) for line in raw_lines if line]
        assert transitions == [("planned", "claimed"), ("claimed", "in_progress")]

    def test_default_wp_events_is_none_folds_to_an_empty_events_file(self, tmp_path: Path) -> None:
        fixture = build_coord_topology_fixture(tmp_path)

        assert (fixture.coord_feature_dir / "status.events.jsonl").read_text(encoding="utf-8") == ""
        assert (fixture.primary_dir / "status.events.jsonl").read_text(encoding="utf-8") == ""


# ---------------------------------------------------------------------------
# T002 -- feature_dir.name -> mission_slug empirical spike
# ---------------------------------------------------------------------------


class TestT002MissionSlugFallbackSpike:
    """Resolves the one still-open empirical unknown named in tracer-design-
    decisions.md's "Open item for WP1" note: does ``feature_dir.name``
    reliably equal (or safely round-trip to) the exact ``mission_slug``
    ``placement_seam`` expects, for a real coord-worktree layout's bare-slug
    vs. composed ``<slug>-<mid8>`` forms?
    """

    def test_bare_mission_slug_resolves_work_package_task_dir_to_primary(self, tmp_path: Path) -> None:
        fixture = build_coord_topology_fixture(tmp_path)

        resolved = placement_seam(fixture.repo_root, fixture.mission_slug).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)

        assert resolved == fixture.primary_dir

    def test_composed_feature_dir_name_also_resolves_to_the_same_primary_dir(self, tmp_path: Path) -> None:
        """CONFIRMED finding (see module docstring + tracer-design-decisions.md's
        dated entry): a coord worktree's ``feature_dir.name`` IS the composed
        ``<slug>-<mid8>`` form (never the bare slug) -- and it resolves via
        ``placement_seam`` to the IDENTICAL primary directory the bare slug
        resolves to (resolution.py's backfilled-primary-dir idempotence path
        absorbs the composed suffix). FR-009's ``feature_dir.name`` fallback
        is therefore safe for this shape; no reproduction needs to pass
        ``mission_slug`` explicitly to route around a mismatch."""
        fixture = build_coord_topology_fixture(tmp_path)
        composed_slug = fixture.coord_feature_dir.name
        assert composed_slug != fixture.mission_slug  # sanity: genuinely the composed form

        resolved = placement_seam(fixture.repo_root, composed_slug).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)

        assert resolved == fixture.primary_dir


# ---------------------------------------------------------------------------
# T003 -- FR-009-isolated reproduction (RED against unmodified production code)
# ---------------------------------------------------------------------------


class TestT003Fr009IsolatedReproduction:
    """Proves the coord-topology reachability bug BY ITSELF, deliberately NOT
    conflated with FR-004's separate, already-known ``_wp_blocks_step``
    ``Lane.UNINITIALIZED`` gap (WP01's fix, not this WP's). See the WP02
    tasks file's Context section for the full isolation rationale."""

    def test_wp_blocks_step_already_correctly_blocks_in_progress_today(self) -> None:
        """Isolation evidence: called directly (no directory I/O, no fixture),
        ``_wp_blocks_step`` ALREADY returns True/blocks for an ``in_progress``
        WP under UNMODIFIED production code -- ``is_run_affecting=True``, not
        in ``{FOR_REVIEW, APPROVED}``, no ``Lane.UNINITIALIZED`` disjunct
        needed. This is what makes the RED result below attributable ONLY to
        the coord-anchoring gap: `_wp_blocks_step`'s own logic was never the
        weak link for this particular lane."""
        state = wp_state_for(Lane.IN_PROGRESS)

        assert _wp_blocks_step("implement", state, has_provenance=False) is True

    def test_should_advance_wp_step_wrongly_permits_advancement_for_coord_feature_dir(self, tmp_path: Path) -> None:
        """RED, pre-fix as originally authored (unmodified production code,
        plain 2-arg call -- at the time this WP was authored standalone, no
        `repo_root`/`mission_slug` keywords existed on
        `_should_advance_wp_step` yet). On this consolidated branch, WP01's
        FR-009 fix has already added those keyword-only parameters to
        `_should_advance_wp_step`; this test deliberately keeps the plain
        2-arg call (omitting them) to exercise the un-anchored code path on
        purpose, not because the keywords are unavailable. `runtime_bridge.py`'s
        own unanchored `tasks_dir = feature_dir /
        "tasks"` read (:753) hits its own no-`tasks/`-dir early return
        (:754-755) on the coord worktree -- confirmed absent by T001's own
        fixture check above -- and returns True (permits advancement) BEFORE
        the per-WP loop that would otherwise call `_wp_blocks_step` (proven
        blocking for this exact lane, above) is ever reached. The WP is
        actively `in_progress`; a correct implementation blocks. WP01's
        FR-009 anchoring flips this to False by resolving `tasks_dir` through
        `mission_runtime.placement_seam(...).read_dir(WORK_PACKAGE_TASK)`
        instead of the raw coord `feature_dir`."""
        fixture = build_coord_topology_fixture(tmp_path, wp_events=claim_and_start_events())
        assert not (fixture.coord_feature_dir / "tasks").is_dir()  # the precondition this bug needs

        result = _should_advance_wp_step("implement", fixture.coord_feature_dir)

        assert result is True, (
            "pre-fix RED: _should_advance_wp_step wrongly permitted advancement "
            "(returned True) for a coord feature_dir carrying an actively "
            "in_progress WP -- the unanchored tasks_dir read never reached the "
            "per-WP loop, so _wp_blocks_step's own (already-correct) blocking "
            "verdict for in_progress was never consulted at all"
        )


# ---------------------------------------------------------------------------
# T004 -- regression pin: the parallel primary-dir call already returns
# correctly, unmodified
# ---------------------------------------------------------------------------


class TestT004RegressionPin:
    def test_should_advance_wp_step_already_correctly_blocks_for_primary_dir(self, tmp_path: Path) -> None:
        """Passes today, unmodified. The SAME `in_progress` event content,
        read directly from `primary_dir` (`tasks/` and `status.events.jsonl`
        co-located there -- no coord split, exactly the shape a flattened /
        `single_branch` mission's `feature_dir` genuinely has), already
        correctly blocks. This is what proves T003's RED is SPECIFICALLY the
        coord-anchoring gap and not `_wp_blocks_step`'s own logic: same
        WP lane, same event content, only the directory split differs."""
        fixture = build_coord_topology_fixture(tmp_path, wp_events=claim_and_start_events())

        result = _should_advance_wp_step("implement", fixture.primary_dir)

        assert result is False
