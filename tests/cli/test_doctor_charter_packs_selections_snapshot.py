"""Snapshot test for the FR-018 Selections section of ``spec-kitty doctor charter-packs``.

WP09 / Mission B analysis-report finding U1 demands a snapshot test so the
operator-facing format of the Selections block stays byte-stable.  The
snapshot lives at ``tests/cli/__snapshots__/doctor_charter_packs_selections.txt``;
any change to its bytes MUST be deliberate (regenerate via the
``UPDATE_SNAPSHOTS=1`` env-var) and reviewed as part of the same commit.

Fixture composition (covers the three required cases from the WP09 DoD):

a) at least one kind with multiple sources (built-in / project / org:<pack>),
b) at least one empty kind rendered as ``(none)``,
c) the exact provenance suffix format.

To minimise environmental coupling the fixture seeds:

* a project charter (``charter.yaml`` ``governance.doctrine`` section) with a
  known selected_<kind> list for two kinds and empty for the rest,
* a single org pack with an ``org-charter.yaml`` declaring one required
  artifact (so the snapshot exercises the ``source: org-required`` branch),
* no project-layer doctrine artifacts (so the project-selected ids fall
  back to ``source: charter`` — distinct from ``source: project`` which
  would require a populated ``.kittify/doctrine/`` tree).

The snapshot pins the rendered text so a future format change cannot
silently regress operator UX.
"""

from __future__ import annotations

import os
import re
import textwrap
from pathlib import Path

import pytest

from specify_cli.cli.commands.doctor import (
    _build_selection_block,
    _render_selection_block_lines,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


SNAPSHOT_PATH: Path = Path(__file__).parent / "__snapshots__" / "doctor_charter_packs_selections.txt"


def _seed_project_charter(repo_root: Path) -> None:
    """Write a deterministic project charter with two non-empty kinds."""
    charter_dir = repo_root / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.md").write_text("# Snapshot Project Charter\n", encoding="utf-8")
    # DIRECTIVE_032 is a known shipped (built-in) directive — selecting it
    # exercises the ``source: built-in`` branch.  PROJECT_DIRECTIVE_01 is
    # NOT in the catalog so it surfaces as ``source: charter`` (declared
    # but not resolved).  Together with the org-required toolguide below
    # this gives the snapshot one kind with multiple sources.
    (charter_dir / "charter.yaml").write_text(
        textwrap.dedent(
            """
            governance:
              charter:
                selected_styleguides:
                  - my-project-styleguide
                  - shared-team-styleguide
                selected_directives:
                  - DIRECTIVE_032
                  - PROJECT_DIRECTIVE_01
            """
        ).lstrip(),
        encoding="utf-8",
    )


def _seed_org_pack(repo_root: Path) -> None:
    """Configure a single org pack with one required toolguide.

    The pack is created on disk so ``load_pack_registry`` accepts it
    (FR-015 hard-fails on missing packs).  The pack ships an empty
    artifact tree plus an ``org-charter.yaml`` declaring one required
    toolguide id — this exercises the ``source: org-required`` branch
    in the snapshot.
    """
    pack_dir = repo_root / "org-pack"
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "org-charter.yaml").write_text(
        textwrap.dedent(
            """
            schema_version: "1"
            org_name: snapshot-org
            required_toolguides:
              - shared-team-toolguide
            """
        ).lstrip(),
        encoding="utf-8",
    )

    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yaml").write_text(
        textwrap.dedent(
            f"""
            charter_packs:
              org:
                packs:
                  - name: snapshot-org-pack
                    local_path: {pack_dir}
            """
        ).lstrip(),
        encoding="utf-8",
    )


def _render_fixture(repo_root: Path) -> str:
    """Build and render the Selections section for the seeded fixture."""
    selections = _build_selection_block(repo_root)
    lines = _render_selection_block_lines(selections)
    return "\n".join(lines) + "\n"


def test_doctor_charter_packs_selections_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The rendered Selections section MUST match the pinned snapshot byte-for-byte."""
    _seed_project_charter(tmp_path)
    _seed_org_pack(tmp_path)

    monkeypatch.chdir(tmp_path)
    actual = _render_fixture(tmp_path)

    # Strip any ANSI / Rich markup that may sneak in if the renderer is
    # later refactored to share code with the Rich console (defensive —
    # the current implementation returns plain strings).
    actual_clean = re.sub(r"\x1b\[[0-9;]*m", "", actual)

    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_PATH.write_text(actual_clean, encoding="utf-8")
        return

    assert SNAPSHOT_PATH.exists(), f"Snapshot file missing at {SNAPSHOT_PATH}. Regenerate with UPDATE_SNAPSHOTS=1 pytest {__file__}"

    expected = SNAPSHOT_PATH.read_text(encoding="utf-8")
    assert actual_clean == expected, (
        "doctor charter-packs Selections section drifted from snapshot.\n"
        f"--- expected ({SNAPSHOT_PATH}) ---\n{expected}\n"
        f"--- actual ---\n{actual_clean}\n"
        "If this change is intentional, regenerate with: "
        f"UPDATE_SNAPSHOTS=1 pytest {__file__}"
    )


def test_selection_kinds_are_the_selection_overlayable_kinds() -> None:
    """The render's ordered kind list covers exactly the authority's set (#5538).

    The reading order is curated, so the list is spelled out; this pins its
    membership so a kind made selection-overlayable in ``ArtifactKind`` cannot
    be silently left out of the Selections block.
    """
    from charter.offering.artifact_kinds import SELECTION_OVERLAYABLE_KIND_FIELDS
    from specify_cli.cli.commands._profile_health_render import _SELECTION_KIND_PLURALS

    assert len(_SELECTION_KIND_PLURALS) == len(set(_SELECTION_KIND_PLURALS))
    assert set(_SELECTION_KIND_PLURALS) == set(SELECTION_OVERLAYABLE_KIND_FIELDS)
