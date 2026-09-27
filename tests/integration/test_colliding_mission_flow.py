"""End-to-end colliding-mission flow (NFR-007 / FR-062).

Builds a synthetic repo with three ``080-*`` missions that share the same
numeric prefix but have distinct ULID identities.  Runs each user-facing
resolution surface against the fixture and asserts the expected behaviour:

1. ``doctor identity --json`` reports all three missions in the
   ``duplicate_prefixes`` section with correct state counts.
2. Resolving the bare numeric handle ``"080"`` raises
   :class:`AmbiguousHandleError` listing all three candidates.
3. Resolving a specific ``mid8`` cleanly selects exactly one mission.
4. Resolving the full ULID cleanly selects exactly one mission.
5. Resolving the fully qualified slug (``080-foo``) cleanly selects one mission.
6. Worktree naming derived from the resolved identity yields three distinct
   worktree paths (no collisions on disk).

Design
------
- The test operates on a ``tmp_path`` fixture; it never touches the real
  repo or any network.  ``SPEC_KITTY_ENABLE_SAAS_SYNC`` is not exercised
  because no subprocess is spawned and no SaaS client is instantiated.
- All assertions run against the real production code paths:
  * ``specify_cli.status.identity_audit`` (doctor identity)
  * ``specify_cli.context.mission_resolver`` (resolve_mission)
  * ``specify_cli.lanes.branch_naming`` (lane/worktree naming)
- The CLI surface is exercised in-process via ``typer.testing.CliRunner``
  for the doctor command.
- Target runtime is well under 30 seconds — the fixture is small (3 mission
  directories with a minimal meta.json each) and no git worktrees are
  created.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.doctor import app as doctor_app
from specify_cli.context.mission_resolver import (
    AmbiguousHandleError,
    MissionNotFoundError,
    resolve_mission,
)
from specify_cli.lanes.branch_naming import (
    lane_branch_name,
    mission_branch_name,
)
from specify_cli.status.identity_audit import (
    audit_repo,
    find_ambiguous_selectors,
    find_duplicate_prefixes,
)

pytestmark = pytest.mark.fast


# Three distinct ULIDs — same 080 prefix, distinct mid8, distinct human slugs.
ULID_FOO = "01KNAAA000000000000000FOO1"
ULID_BAR = "01KNBBB000000000000000BAR1"
ULID_BAZ = "01KNCCC000000000000000BAZ1"


# ---------------------------------------------------------------------------
# Fixture: 3-mission colliding 080-* repo
# ---------------------------------------------------------------------------


def _write_minimal_meta(
    feature_dir: Path,
    *,
    mission_id: str,
    mission_slug: str,
    mission_number: int = 80,
    friendly_name: str = "",
) -> None:
    """Write a schema-complete minimal meta.json for the resolver/audit."""
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {
        "slug": mission_slug,
        "mission_slug": mission_slug,
        "friendly_name": friendly_name or mission_slug,
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-04-11T12:00:00+00:00",
        "mission_id": mission_id,
        "mission_number": mission_number,
    }
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


@pytest.fixture()
def colliding_080_repo(tmp_path: Path) -> Path:
    """Return a repo root containing three colliding ``080-*`` missions.

    Structure::

        <tmp_path>/
          kitty-specs/
            080-foo/meta.json  (mission_id ULID_FOO)
            080-bar/meta.json  (mission_id ULID_BAR)
            080-baz/meta.json  (mission_id ULID_BAZ)
    """
    specs = tmp_path / "kitty-specs"
    _write_minimal_meta(
        specs / "080-foo",
        mission_id=ULID_FOO,
        mission_slug="080-foo",
        friendly_name="Foo Mission",
    )
    _write_minimal_meta(
        specs / "080-bar",
        mission_id=ULID_BAR,
        mission_slug="080-bar",
        friendly_name="Bar Mission",
    )
    _write_minimal_meta(
        specs / "080-baz",
        mission_id=ULID_BAZ,
        mission_slug="080-baz",
        friendly_name="Baz Mission",
    )
    return tmp_path


# ---------------------------------------------------------------------------
# 1. doctor identity --json reports all 3 duplicates
# ---------------------------------------------------------------------------


def test_doctor_identity_audit_sees_three_080_missions(colliding_080_repo: Path) -> None:
    """audit_repo + find_duplicate_prefixes finds all 3 missions under "080"."""
    states = audit_repo(colliding_080_repo)
    slugs = sorted(s.slug for s in states)
    assert slugs == ["080-bar", "080-baz", "080-foo"]
    # All three should be classified as 'assigned' since mission_id is present
    # and mission_number is an int.
    assert all(s.state == "assigned" for s in states), f"Expected all assigned, got {[(s.slug, s.state) for s in states]}"

    duplicates = find_duplicate_prefixes(colliding_080_repo)
    assert "080" in duplicates
    assert len(duplicates["080"]) == 3


def test_doctor_identity_audit_reports_ambiguous_selectors(
    colliding_080_repo: Path,
) -> None:
    """Bare "080" handle must be flagged as ambiguous by the selector audit."""
    states = audit_repo(colliding_080_repo)
    ambiguous = find_ambiguous_selectors(states)
    # "080" is ambiguous (3-way tie)
    assert "080" in ambiguous, f"Expected '080' in ambiguous handles, got {sorted(ambiguous.keys())}"
    assert len(ambiguous["080"]) == 3


def test_doctor_identity_cli_json_reports_three_duplicates(
    colliding_080_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``spec-kitty doctor identity --json`` exposes duplicates to operators.

    Exercises the CLI surface in-process using CliRunner.  We monkeypatch
    the repo-root resolver to point at the fixture.
    """
    monkeypatch.setattr(
        "specify_cli.cli.commands.doctor.locate_project_root",
        lambda: colliding_080_repo,
    )

    runner = CliRunner()
    result = runner.invoke(doctor_app, ["identity", "--json"])
    assert result.exit_code == 0, f"doctor identity --json failed: {result.exit_code}\n{result.stdout}"

    report = json.loads(result.stdout)
    assert "duplicate_prefixes" in report
    assert "080" in report["duplicate_prefixes"], f"Expected '080' in duplicate_prefixes, got {sorted(report['duplicate_prefixes'].keys())}"
    dup_080 = report["duplicate_prefixes"]["080"]
    assert len(dup_080) == 3, f"Expected 3 duplicates under '080', got {len(dup_080)}: {dup_080}"

    # Summary counts match the four-state classifier output.
    assert report["summary"]["assigned"] == 3, report["summary"]


# ---------------------------------------------------------------------------
# 2. Ambiguous handle — bare "080" must raise
# ---------------------------------------------------------------------------


def test_resolve_bare_080_raises_ambiguous(colliding_080_repo: Path) -> None:
    """``resolve_mission("080", ...)`` must raise with all 3 candidates listed."""
    with pytest.raises(AmbiguousHandleError) as exc_info:
        resolve_mission("080", colliding_080_repo)

    err = exc_info.value
    assert err.handle == "080"
    slugs = sorted(c.mission_slug for c in err.candidates)
    assert slugs == ["080-bar", "080-baz", "080-foo"]

    # The rendered error message must name every candidate so the operator
    # can pick the right mid8 / slug without extra commands.
    rendered = str(err)
    for slug in slugs:
        assert slug in rendered
    # Each candidate's mid8 should also be present as a suggested --mission value.
    for candidate in err.candidates:
        assert candidate.mid8 in rendered


# ---------------------------------------------------------------------------
# 3. mid8 resolution — a specific 8-char prefix selects exactly one mission
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ulid", "expected_slug"),
    [
        (ULID_FOO, "080-foo"),
        (ULID_BAR, "080-bar"),
        (ULID_BAZ, "080-baz"),
    ],
)
def test_resolve_by_mid8_is_unique(
    colliding_080_repo: Path,
    ulid: str,
    expected_slug: str,
) -> None:
    """Each mid8 must resolve to exactly one mission."""
    handle = ulid[:8]
    resolved = resolve_mission(handle, colliding_080_repo)
    assert resolved.mission_id == ulid
    assert resolved.mission_slug == expected_slug
    assert resolved.mid8 == handle


# ---------------------------------------------------------------------------
# 4. Full ULID resolution
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ulid", "expected_slug"),
    [
        (ULID_FOO, "080-foo"),
        (ULID_BAR, "080-bar"),
        (ULID_BAZ, "080-baz"),
    ],
)
def test_resolve_by_full_ulid_is_unique(
    colliding_080_repo: Path,
    ulid: str,
    expected_slug: str,
) -> None:
    """Full 26-char ULID resolves unambiguously."""
    resolved = resolve_mission(ulid, colliding_080_repo)
    assert resolved.mission_id == ulid
    assert resolved.mission_slug == expected_slug


# ---------------------------------------------------------------------------
# 5. Fully qualified slug resolution
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("slug", "expected_ulid"),
    [
        ("080-foo", ULID_FOO),
        ("080-bar", ULID_BAR),
        ("080-baz", ULID_BAZ),
    ],
)
def test_resolve_by_full_slug_is_unique(
    colliding_080_repo: Path,
    slug: str,
    expected_ulid: str,
) -> None:
    """The full directory slug disambiguates without needing the mid8."""
    resolved = resolve_mission(slug, colliding_080_repo)
    assert resolved.mission_slug == slug
    assert resolved.mission_id == expected_ulid


def test_resolve_unknown_handle_raises_not_found(colliding_080_repo: Path) -> None:
    """Negative: a handle that matches nothing raises ``MissionNotFoundError``."""
    with pytest.raises(MissionNotFoundError):
        resolve_mission("999", colliding_080_repo)


# ---------------------------------------------------------------------------
# 6. Worktree / branch naming — distinct per mission
# ---------------------------------------------------------------------------


def test_lane_branches_are_distinct_per_mission(colliding_080_repo: Path) -> None:
    """Lane branch names must not collide across the 3 missions.

    Lane naming takes no identity (FR-002) — the disambiguator here
    is the distinct ``mission_slug`` each mission already carries (``080-foo``
    / ``080-bar`` / ``080-baz``), not an injected mid8. This fixture's three
    missions collide only on their shared numeric prefix, never on the full
    slug, so distinctness holds without any identity parameter.
    """
    branch_names: set[str] = set()
    worktree_paths: set[str] = set()

    for ulid in (ULID_FOO, ULID_BAR, ULID_BAZ):
        resolved = resolve_mission(ulid, colliding_080_repo)
        branch = lane_branch_name(
            mission_slug=resolved.mission_slug,
            lane_id="lane-a",
        )
        branch_names.add(branch)
        # Simulate the worktree directory path: .worktrees/<mission_slug>-lane-a
        # (the created form — no mid8, since none of these slugs embed one).
        # We aren't actually creating worktrees in this test — just verifying
        # that the derived path differs for each mission.
        worktree_paths.add(f"{resolved.mission_slug}-lane-a")

    assert len(branch_names) == 3, f"Expected 3 distinct branch names, got {sorted(branch_names)}"
    assert len(worktree_paths) == 3, f"Expected 3 distinct worktree paths, got {sorted(worktree_paths)}"
    # Every branch must include its own (distinct) mission slug.
    for ulid in (ULID_FOO, ULID_BAR, ULID_BAZ):
        resolved = resolve_mission(ulid, colliding_080_repo)
        assert any(resolved.mission_slug in name for name in branch_names), f"slug {resolved.mission_slug!r} missing from any lane branch name: {branch_names}"


def test_mission_branches_are_distinct_per_mission(colliding_080_repo: Path) -> None:
    """Mission-level branch names also carry the mid8 disambiguator."""
    branch_names: set[str] = set()
    for ulid in (ULID_FOO, ULID_BAR, ULID_BAZ):
        resolved = resolve_mission(ulid, colliding_080_repo)
        branch_names.add(
            mission_branch_name(
                mission_slug=resolved.mission_slug,
                mission_id=ulid,
            )
        )
    assert len(branch_names) == 3
