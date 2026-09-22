"""#4868 (P1): ``issue-verdict`` on a coord mission with a legacy ``.md`` on
its authoritative COORD surface must PRESERVE existing verdicts (FR-010..014,
FR-018, US4/US5, C-011).

The defect (grounding-4868.md): ``_migrate_if_needed`` resolves the coord-aware
``read_dir`` correctly, but hands the PRIMARY ``feature_dir`` (not ``read_dir``)
to :func:`migrate_issue_matrix_to_json`, which then looks for the legacy
``issue-matrix.md`` on the PRIMARY surface (where it does not exist under coord
topology), returns ``None`` (``migrated=False``), and the subsequent full-object
write serializes ONLY the newly-recorded row -- silently dropping every prior
verdict.

This suite is an INTEGRATION test on purpose (grounding-4868.md "Red-first"):
it drives the REAL write-seam (``write_artifact`` -> ``commit_for_mission``),
because a faked ``write_artifact`` writes only the primary copy and never
materializes the coord JSON -- the post-migration coord re-read would then be
empty even with the fix, masking the very behaviour under test.

The coord-topology fixture (``_build_coord_mission_for_matrix``) is reused
verbatim from ``tests/integration/test_accept_matrix_coord_partition.py`` (C-001
-- one canonical coord-fixture construction sequence, not a parallel one); that
file is NOT edited here.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionArtifactKind, coord_read_dir_for
from specify_cli.cli.commands.agent.issue_verdict import IssueVerdictError, do_issue_verdict
from specify_cli.tasks.issue_matrix_migration import load_issue_matrix

# Reused verbatim -- do NOT duplicate the coord-fixture construction sequence
# (see module docstring / C-001).
from tests.integration.test_accept_matrix_coord_partition import _build_coord_mission_for_matrix

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_LEGACY_MD_HEADER = "# Issue Matrix\n\n| Issue | Title | Verdict | Evidence ref |\n|-------|-------|---------|--------------|\n"


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo_root), *args], capture_output=True, text=True, check=True)


def _seed_coord_legacy_md(coord_root: Path, coord_feature_dir: Path, body: str) -> None:
    """Write + commit a legacy ``issue-matrix.md`` on the COORD surface.

    Materializes the lazily-created coord ``kitty-specs/<slug>/`` dir and commits
    the markdown on the coordination branch (the coord worktree ``coord_root`` is
    already checked out on that branch by the fixture) -- so the authoritative
    read surface genuinely carries the legacy matrix, exactly as a real
    pre-JSON coord mission does.
    """
    coord_feature_dir.mkdir(parents=True, exist_ok=True)
    md_path = coord_feature_dir / "issue-matrix.md"
    md_path.write_text(body, encoding="utf-8")
    _git(coord_root, "add", str(md_path.relative_to(coord_root)))
    _git(coord_root, "commit", "-m", "chore: seed legacy issue-matrix.md on coord")


def _coord_read_dir(repo_root: Path, mission_slug: str) -> Path:
    read_dir = coord_read_dir_for(repo_root, mission_slug, MissionArtifactKind.ISSUE_MATRIX)
    assert read_dir is not None, (
        "fixture invariant: coord_read_dir_for must resolve the coord surface for a materialized coord-topology mission (else this whole test is vacuous)"
    )
    return read_dir


# ===========================================================================
# T007 -- the core red->green: prior coord verdict survives a new one
# ===========================================================================


def test_coord_legacy_md_verdict_is_preserved_when_recording_a_new_issue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """US4 S1/S2: recording #B must migrate the coord ``.md`` and KEEP #A.

    RED on base: the migration reads the (empty) PRIMARY surface, ``migrated`` is
    ``False``, and the committed coord JSON carries ONLY #B -- #A is dropped.
    """
    result, coord_root, coord_feature_dir = _build_coord_mission_for_matrix(tmp_path)
    slug = result.mission_slug

    _seed_coord_legacy_md(
        coord_root,
        coord_feature_dir,
        _LEGACY_MD_HEADER + "| #A | Pre-existing | fixed | commit aaa111 |\n",
    )

    # Precondition: the canonical reader sees #A on the coord surface BEFORE the call.
    read_dir = _coord_read_dir(tmp_path, slug)
    before = {row.issue: row for row in load_issue_matrix(read_dir)}
    assert "#A" in before, f"fixture invariant: #A must be readable on coord pre-call, got {list(before)}"

    monkeypatch.chdir(tmp_path)
    payload = do_issue_verdict(
        mission=slug,
        issue="#B",
        verdict="fixed",
        actor="claude",
        evidence_ref="commit bbb222",
        repo_root=tmp_path,
    )

    assert payload["ok"] is True, payload
    assert payload["migrated"] is True, (
        f"the legacy coord .md must be migrated on this first structured write (read from the coord surface, not the empty primary): {payload}"
    )

    # The committed coord issue-matrix.json (resolved via coord_read_dir_for,
    # never a hand-rolled -coord path) must carry BOTH rows.
    read_dir_after = _coord_read_dir(tmp_path, slug)
    committed_json = read_dir_after / "issue-matrix.json"
    assert committed_json.exists(), f"coord issue-matrix.json not committed at {committed_json}"

    after = {row.issue: row for row in load_issue_matrix(read_dir_after)}
    assert set(after) == {"#A", "#B"}, f"prior verdict dropped: expected both #A and #B on the coord surface, got {list(after)}"
    assert after["#A"].verdict.value == "fixed"
    assert after["#A"].evidence_ref == "commit aaa111", "evidence for the preserved row must survive"
    assert after["#B"].verdict.value == "fixed"


# ===========================================================================
# T008 -- mutation-killing write-staging spy (C-011 / C-4868-write-staging)
# ===========================================================================


def test_migration_write_is_staged_on_primary_not_coord(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C-011 killer assertion: the migration's write stays staged on PRIMARY.

    A bare "no primary residue" check is INSUFFICIENT (the untouched main write
    cleans residue for the wrong fix too). This spies on the migration's
    ``write_issue_matrix`` and asserts it received ``feature_dir == primary``.

    Falsifiability (verified manually, see PR):
    - base:  migration reads the empty primary surface, returns ``None`` -> the
      migration write is NEVER invoked -> ``recorded == []`` (RED).
    - ``read_dir``-as-write mutant: the migration writes with
      ``feature_dir == coord`` -> ``recorded == [coord_feature_dir]`` (RED).
    - fix:   ``recorded == [primary]`` (GREEN).
    """
    result, coord_root, coord_feature_dir = _build_coord_mission_for_matrix(tmp_path)
    slug = result.mission_slug

    _seed_coord_legacy_md(
        coord_root,
        coord_feature_dir,
        _LEGACY_MD_HEADER + "| #A | Pre-existing | fixed | commit aaa111 |\n",
    )

    import specify_cli.tasks.issue_matrix_migration as migration_mod

    real_write = migration_mod.write_issue_matrix
    recorded_feature_dirs: list[Path] = []

    def _spy_write(*, feature_dir: Path, **kwargs: object):  # type: ignore[no-untyped-def]
        recorded_feature_dirs.append(feature_dir)
        return real_write(feature_dir=feature_dir, **kwargs)

    monkeypatch.setattr(migration_mod, "write_issue_matrix", _spy_write)

    monkeypatch.chdir(tmp_path)
    payload = do_issue_verdict(
        mission=slug,
        issue="#B",
        verdict="fixed",
        actor="claude",
        evidence_ref="commit bbb222",
        repo_root=tmp_path,
    )

    assert payload["ok"] is True and payload["migrated"] is True, payload
    assert recorded_feature_dirs == [result.feature_dir], (
        "the migration must read the coord surface but STAGE its write on the PRIMARY "
        "feature_dir (C-011: the write-seam materializes coord + cleans residue). "
        f"expected exactly one migration write staged on {result.feature_dir}, "
        f"got {recorded_feature_dirs}"
    )
    assert coord_feature_dir not in recorded_feature_dirs


# ===========================================================================
# T008 -- second-call idempotency (C-4868-idempotent, FR-018)
# ===========================================================================


def test_second_verdict_after_migration_preserves_all_rows_no_primary_residue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """US4 S3: once the coord JSON exists, a further verdict is not a re-migrate.

    The 2nd call reports ``migrated=False``, all of #A/#B/#C survive on coord,
    and no ``issue-matrix.json`` residue is left on the primary surface.
    """
    result, coord_root, coord_feature_dir = _build_coord_mission_for_matrix(tmp_path)
    slug = result.mission_slug

    _seed_coord_legacy_md(
        coord_root,
        coord_feature_dir,
        _LEGACY_MD_HEADER + "| #A | Pre-existing | fixed | commit aaa111 |\n",
    )

    monkeypatch.chdir(tmp_path)
    first = do_issue_verdict(
        mission=slug,
        issue="#B",
        verdict="fixed",
        actor="claude",
        evidence_ref="commit bbb222",
        repo_root=tmp_path,
    )
    assert first["migrated"] is True, first

    second = do_issue_verdict(
        mission=slug,
        issue="#C",
        verdict="in-mission",
        actor="claude",
        evidence_ref="WP07 in progress",
        repo_root=tmp_path,
    )
    assert second["ok"] is True, second
    assert second["migrated"] is False, f"the coord JSON already exists after the first write -- the second call must NOT re-migrate: {second}"

    read_dir = _coord_read_dir(tmp_path, slug)
    after = {row.issue: row for row in load_issue_matrix(read_dir)}
    assert set(after) == {"#A", "#B", "#C"}, f"a prior row was dropped by the 2nd write: {list(after)}"
    assert after["#A"].verdict.value == "fixed"
    assert after["#B"].verdict.value == "fixed"
    assert after["#C"].verdict.value == "in-mission"

    assert not (result.feature_dir / "issue-matrix.json").exists(), (
        "no primary issue-matrix.json residue must remain after a coord-topology write (the write-seam cleans the primary staging copy)"
    )


# ===========================================================================
# T008 -- malformed legacy .md -> structured error (C-4868-malformed)
# ===========================================================================


def test_malformed_coord_legacy_md_raises_structured_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-018: a malformed authoritative ``.md`` yields a structured
    :class:`IssueVerdictError`, never a raw traceback and never a silent
    empty migration that would drop every row.

    RED on base: the migration reads the empty PRIMARY surface, never sees the
    malformed coord ``.md``, returns ``None``, and the command succeeds while
    silently writing only the new row (no error raised).
    """
    result, coord_root, coord_feature_dir = _build_coord_mission_for_matrix(tmp_path)
    slug = result.mission_slug

    # Two Markdown tables -> structurally malformed (ISSUE_MATRIX_MULTI_TABLE):
    # the legacy parser rejects it and yields zero rows, so a naive migration
    # would silently serialize an empty matrix (row loss).
    _seed_coord_legacy_md(
        coord_root,
        coord_feature_dir,
        _LEGACY_MD_HEADER + "| #A | Pre-existing | fixed | commit aaa111 |\n\n" + _LEGACY_MD_HEADER + "| #Z | Second table | fixed | commit zzz999 |\n",
    )

    monkeypatch.chdir(tmp_path)
    with pytest.raises(IssueVerdictError) as excinfo:
        do_issue_verdict(
            mission=slug,
            issue="#B",
            verdict="fixed",
            actor="claude",
            evidence_ref="commit bbb222",
            repo_root=tmp_path,
        )

    assert excinfo.value.code == "malformed_legacy_matrix", excinfo.value.code
    # The malformed .md must NOT have been silently migrated to an empty JSON.
    assert not (coord_feature_dir / "issue-matrix.json").exists(), "a malformed .md must not be silently migrated to a (lossy) empty JSON"
