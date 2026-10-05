"""Seam test for ``specify_cli.consolidation.bookkeeping_projection`` (mission #2057, WP09).

Covers the security-sensitive path-trust assertions (trusted AND rejected
branches) and the surviving coord→target projection helpers. The
final-bookkeeping snapshot/restore compensator that used to live in this module
was RETIRED by the lifecycle-gate-execution-context mission (WP09 / T048 / TAO-3):
the merge executor now enrols its bytes with the SINGLE owner compensator in
``coordination.atomic_write``, so the compensator round-trip / trust tests below
re-point onto that owner surface (same byte-identical semantics). The
re-export-identity and one-way-import guards live in the consolidated
``tests/consolidation/test_merge_compat_surface.py``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.coordination import atomic_write as aw
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.consolidation import bookkeeping_projection as bp
from specify_cli.consolidation.git_probes import GitProbeError, driver_replay_expected_bytes

pytestmark = pytest.mark.fast


def test_restore_generated_artifact_snapshots_signature_stable() -> None:
    """TAO-3: the ONE owner compensator restores from a single dict positional arg."""
    import inspect

    sig = inspect.signature(aw.restore_generated_artifact_snapshots)
    params = list(sig.parameters)
    assert params[0] == "snapshots"


# --- _validate_mission_slug_path_segment ------------------------------------


def test_validate_mission_slug_accepts_safe_segment() -> None:
    assert bp._validate_mission_slug_path_segment("my-mission-01ABC") == "my-mission-01ABC"


def test_validate_mission_slug_rejects_traversal() -> None:
    with pytest.raises(ValueError):
        bp._validate_mission_slug_path_segment("../escape")


# --- snapshot capture / restore round-trip ----------------------------------


def _repo_with_spec(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / KITTY_SPECS_DIR / "m").mkdir(parents=True)
    return repo


def test_capture_and_restore_round_trip(tmp_path: Path) -> None:
    repo = _repo_with_spec(tmp_path)
    events = repo / KITTY_SPECS_DIR / "m" / "status.events.jsonl"
    events.write_text("ORIGINAL\n", encoding="utf-8")

    roots = [repo / KITTY_SPECS_DIR]
    snapshots = aw.capture_generated_artifact_snapshots(events, trusted_roots=roots)
    # Mutate, then restore through the single owner compensator.
    events.write_text("MUTATED\n", encoding="utf-8")
    aw.restore_generated_artifact_snapshots(snapshots)
    assert events.read_text(encoding="utf-8") == "ORIGINAL\n"


def test_capture_restore_recreates_deleted_file(tmp_path: Path) -> None:
    repo = _repo_with_spec(tmp_path)
    events = repo / KITTY_SPECS_DIR / "m" / "status.events.jsonl"
    # Absent at capture time -> snapshot is None -> restore must remove it.
    roots = [repo / KITTY_SPECS_DIR]
    snapshots = aw.capture_generated_artifact_snapshots(events, trusted_roots=roots)
    events.write_text("CREATED-AFTER-CAPTURE\n", encoding="utf-8")
    aw.restore_generated_artifact_snapshots(snapshots)
    assert not events.exists()


# --- path-trust: trusted + rejected branches (owner containment) -------------


def test_snapshot_trust_accepts_kitty_specs(tmp_path: Path) -> None:
    repo = _repo_with_spec(tmp_path)
    candidate = repo / KITTY_SPECS_DIR / "m" / "status.json"
    snapshots = aw.capture_generated_artifact_snapshots(
        candidate, trusted_roots=[repo / KITTY_SPECS_DIR]
    )
    assert candidate.resolve(strict=False) in snapshots


def test_snapshot_trust_rejects_outside_path(tmp_path: Path) -> None:
    repo = _repo_with_spec(tmp_path)
    outside = tmp_path / "elsewhere" / "evil.json"
    with pytest.raises(ValueError):
        aw.capture_generated_artifact_snapshots(
            outside, trusted_roots=[repo / KITTY_SPECS_DIR]
        )


def test_status_surface_trust_accepts_kitty_specs(tmp_path: Path) -> None:
    repo = _repo_with_spec(tmp_path)
    surface = repo / KITTY_SPECS_DIR / "m"
    with patch.object(bp, "get_main_repo_root", lambda _r: repo):
        trusted = bp._assert_status_surface_path_is_trusted(repo_root=repo, status_feature_dir=surface)
    assert trusted == surface.resolve()


def test_status_surface_trust_rejects_topology_mismatch(tmp_path: Path) -> None:
    """A worktrees-shaped segment that resolves outside the worktrees root is rejected."""
    repo = _repo_with_spec(tmp_path)
    # A path under kitty-specs but named like a worktrees path is a mismatch.
    bogus = repo / "not-real-root" / "x"
    with (
        patch.object(bp, "get_main_repo_root", lambda _r: repo),
        pytest.raises(ValueError, match="Untrusted status surface path"),
    ):
        bp._assert_status_surface_path_is_trusted(repo_root=repo, status_feature_dir=bogus)


def test_status_surface_file_trust_rejects_bad_filename(tmp_path: Path) -> None:
    repo = _repo_with_spec(tmp_path)
    surface = repo / KITTY_SPECS_DIR / "m"
    with (
        patch.object(bp, "get_main_repo_root", lambda _r: repo),
        pytest.raises(ValueError, match="Refusing untrusted status filename"),
    ):
        bp._assert_status_surface_file_path_is_trusted(
            repo_root=repo, status_feature_dir=surface, filename="evil.txt"
        )


# --- _target_branch_still_at_baseline ---------------------------------------


def test_target_branch_still_at_baseline(tmp_path: Path) -> None:
    assert bp._target_branch_still_at_baseline(tmp_path, "main", "") is False
    assert bp._target_branch_still_at_baseline(tmp_path, "main", "HEAD~1") is False
    with patch.object(bp, "run_command", return_value=(0, "abc123", "")):
        assert bp._target_branch_still_at_baseline(tmp_path, "main", "abc123") is True
        assert bp._target_branch_still_at_baseline(tmp_path, "main", "deadbeef") is False
    with patch.object(bp, "run_command", return_value=(1, "", "err")):
        assert bp._target_branch_still_at_baseline(tmp_path, "main", "abc123") is False


# --- _project_status_bookkeeping_to_target (non-worktree fast path) ----------


def test_project_returns_target_paths_when_not_worktree(tmp_path: Path) -> None:
    repo = _repo_with_spec(tmp_path)
    surface = repo / KITTY_SPECS_DIR / "m"
    with patch.object(bp, "get_main_repo_root", lambda _r: repo):
        events, status = bp._project_status_bookkeeping_to_target(
            main_repo=repo, mission_slug="m", status_feature_dir=surface
        )
    assert events.name == "status.events.jsonl"
    assert status.name == "status.json"


# --- driver-replay attribution probe (#5038, terminus-projection-driver-replay) --
#
# Real, on-disk git repos throughout (no git-layer mocking): the probe shells out
# to ``git show``/``git check-attr`` and invokes the ACTUAL registered
# ``consolidation.drivers`` bodies (relocated there from ``cli.commands.merge_driver``
# by #5119), so a mock would prove nothing about whether the replay genuinely
# matches what a real squash would do.


def _driver_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _driver_rev(repo: Path, ref: str) -> str:
    return _driver_git(repo, "rev-parse", ref).stdout.strip()


def _init_driver_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "driver-repo"
    repo.mkdir()
    _driver_git(repo, "init", "-q", "-b", "main")
    _driver_git(repo, "config", "user.email", "t@example.com")
    _driver_git(repo, "config", "user.name", "Test")
    _driver_git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _driver_git(repo, "add", "-A")
    _driver_git(repo, "commit", "-q", "-m", "seed")
    return repo


def _commit_trace(repo: Path, trace_rel: str, body: str, msg: str) -> None:
    path = repo / trace_rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    _driver_git(repo, "add", "-A")
    _driver_git(repo, "commit", "-q", "-m", msg)


@pytest.mark.git_repo
def test_driver_replay_pass_on_lossless_union(tmp_path: Path) -> None:
    """FR-001: a diverged, driver-governed path PASSes when the landed blob IS
    the registered driver's own replayed output (a legitimate lossless union)."""
    repo = _init_driver_repo(tmp_path)
    trace_rel = "kitty-specs/m/traces/WP01.md"
    _commit_trace(repo, trace_rel, "baseline\n", "checkpoint")
    checkpoint = _driver_rev(repo, "main")

    _commit_trace(repo, trace_rel, "baseline\ntarget edit\n", "target update")
    pre_squash_target = _driver_rev(repo, "main")

    _driver_git(repo, "branch", "coord", checkpoint)
    _driver_git(repo, "checkout", "-q", "coord")
    _commit_trace(repo, trace_rel, "baseline\ncoord edit\n", "coord update")
    _driver_git(repo, "checkout", "-q", "main")

    expected = driver_replay_expected_bytes(
        repo, trace_rel, base_ref=checkpoint, ours_ref=pre_squash_target, theirs_ref="coord"
    )
    landed_path = repo / trace_rel
    landed_path.write_bytes(expected)
    _driver_git(repo, "add", "-A")
    _driver_git(repo, "commit", "-q", "-m", "landed the driver's real output")

    assert bp.projected_content_matches_target(
        main_repo=repo,
        coord_ref="coord",
        target_ref="main",
        projected_paths=(trace_rel,),
        checkpoint_sha=checkpoint,
        pre_squash_target_ref=pre_squash_target,
    )


@pytest.mark.git_repo
def test_driver_replay_refuses_on_dropped_content(tmp_path: Path) -> None:
    """FR-002 / INV-FLOOR-1: REFUSE when the landed blob is NOT the driver's
    replayed output -- here the target's own edit is silently dropped."""
    repo = _init_driver_repo(tmp_path)
    trace_rel = "kitty-specs/m/traces/WP01.md"
    _commit_trace(repo, trace_rel, "baseline\n", "checkpoint")
    checkpoint = _driver_rev(repo, "main")

    _commit_trace(repo, trace_rel, "baseline\ntarget edit\n", "target update")
    pre_squash_target = _driver_rev(repo, "main")

    _driver_git(repo, "branch", "coord", checkpoint)
    _driver_git(repo, "checkout", "-q", "coord")
    _commit_trace(repo, trace_rel, "baseline\ncoord edit\n", "coord update")
    _driver_git(repo, "checkout", "-q", "main")

    # Genuinely-lossy landing: coord bytes verbatim, dropping the target edit --
    # NOT what the union driver would ever produce.
    _commit_trace(repo, trace_rel, "baseline\ncoord edit\n", "genuinely-lossy landing")

    assert not bp.projected_content_matches_target(
        main_repo=repo,
        coord_ref="coord",
        target_ref="main",
        projected_paths=(trace_rel,),
        checkpoint_sha=checkpoint,
        pre_squash_target_ref=pre_squash_target,
    )


@pytest.mark.git_repo
def test_driver_replay_refuses_when_no_registered_driver(tmp_path: Path) -> None:
    """FR-003 / INV-FLOOR-2: a diverged path with NO registered merge driver
    REFUSEs fail-closed rather than passing vacuously."""
    repo = _init_driver_repo(tmp_path)
    notes_rel = "kitty-specs/m/notes/some-note.md"  # not in _MERGE_DRIVERS' patterns
    _commit_trace(repo, notes_rel, "baseline\n", "checkpoint")
    checkpoint = _driver_rev(repo, "main")

    _commit_trace(repo, notes_rel, "baseline\ntarget edit\n", "target update")
    pre_squash_target = _driver_rev(repo, "main")

    _driver_git(repo, "branch", "coord", checkpoint)
    _driver_git(repo, "checkout", "-q", "coord")
    _commit_trace(repo, notes_rel, "baseline\ncoord edit\n", "coord update")
    _driver_git(repo, "checkout", "-q", "main")

    # Whatever a real, driver-less squash would land here, the proof cannot
    # evaluate it (no registered driver to replay) -- REFUSE, never PASS.
    _commit_trace(repo, notes_rel, "baseline\ntarget edit\ncoord edit\n", "auto-merged landing")

    assert not bp.projected_content_matches_target(
        main_repo=repo,
        coord_ref="coord",
        target_ref="main",
        projected_paths=(notes_rel,),
        checkpoint_sha=checkpoint,
        pre_squash_target_ref=pre_squash_target,
    )


@pytest.mark.git_repo
def test_driver_replay_probe_raises_on_missing_blob(tmp_path: Path) -> None:
    """FR-003: the probe itself REFUSEs fail-closed (raises ``GitProbeError``)
    when the ``theirs`` blob cannot be read at the given ref."""
    repo = _init_driver_repo(tmp_path)
    seed_sha = _driver_rev(repo, "main")  # the file does not exist yet here
    trace_rel = "kitty-specs/m/traces/WP01.md"
    _commit_trace(repo, trace_rel, "baseline\n", "checkpoint")
    checkpoint = _driver_rev(repo, "main")
    _commit_trace(repo, trace_rel, "baseline\ntarget edit\n", "target update")
    pre_squash_target = _driver_rev(repo, "main")

    with pytest.raises(GitProbeError):
        # ``seed_sha`` predates the file's existence -- absent as ``theirs``.
        driver_replay_expected_bytes(
            repo, trace_rel, base_ref=checkpoint, ours_ref=pre_squash_target, theirs_ref=seed_sha
        )


@pytest.mark.git_repo
def test_driver_replay_preserves_non_diverged_pass(tmp_path: Path) -> None:
    """FR-004 / INV-NO-REGRESSION: a path the target never touched after the
    checkpoint keeps PASSing via the original byte-equality proof -- no driver
    lookup needed at all (proven with a path that has none registered)."""
    repo = _init_driver_repo(tmp_path)
    notes_rel = "kitty-specs/m/notes/some-note.md"
    _commit_trace(repo, notes_rel, "baseline\n", "checkpoint")
    checkpoint = _driver_rev(repo, "main")
    # Target never diverges: its pre-squash tip IS the checkpoint.
    pre_squash_target = checkpoint

    _driver_git(repo, "branch", "coord", checkpoint)
    _driver_git(repo, "checkout", "-q", "coord")
    _commit_trace(repo, notes_rel, "baseline\ncoord-only addition\n", "coord update")
    _driver_git(repo, "checkout", "-q", "main")

    # The coord content lands verbatim (no divergence to reconcile).
    _commit_trace(repo, notes_rel, "baseline\ncoord-only addition\n", "project coord content")

    assert bp.projected_content_matches_target(
        main_repo=repo,
        coord_ref="coord",
        target_ref="main",
        projected_paths=(notes_rel,),
        checkpoint_sha=checkpoint,
        pre_squash_target_ref=pre_squash_target,
    )


# --- coordination_alias_files / assert_alias_events_preserved (#5651) --------

_ALIAS_SLUG = "alias-seam"
_ALIAS_DIR = f"{_ALIAS_SLUG}-01KX0000"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _alias_main_repo(tmp_path: Path, *, with_primary_dir: bool = True, files: dict[str, str] | None = None) -> Path:
    """A git repository whose composed directory holds ``files`` (all tracked, in one commit)."""
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    _git(tmp_path, "config", "user.email", "t@t.com")
    _git(tmp_path, "config", "user.name", "T")
    _git(tmp_path, "config", "commit.gpgsign", "false")
    if with_primary_dir:
        (tmp_path / KITTY_SPECS_DIR / _ALIAS_SLUG).mkdir(parents=True)
    (tmp_path / KITTY_SPECS_DIR / _ALIAS_DIR).mkdir(parents=True)
    for relpath, content in (files or {}).items():
        target = tmp_path / KITTY_SPECS_DIR / _ALIAS_DIR / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    if files:
        _git(tmp_path, "add", ".")
        _git(tmp_path, "commit", "-qm", "init")
    return tmp_path


def _coord_status_dir(main_repo: Path, name: str) -> Path:
    return main_repo / ".worktrees" / f"{_ALIAS_DIR}-coord" / KITTY_SPECS_DIR / name


def _alias_files(repo: Path, status_dir_name: str = _ALIAS_DIR, *, slug: str = _ALIAS_SLUG) -> bp.AliasFiles | None:
    return bp.coordination_alias_files(main_repo=repo, mission_slug=slug, status_feature_dir=_coord_status_dir(repo, status_dir_name))


def test_alias_files_returns_every_tracked_coordination_kind_file_sorted(tmp_path: Path) -> None:
    repo = _alias_main_repo(
        tmp_path,
        files={"status.json": "{}", "status.events.jsonl": "", "traces/b.md": "b", "traces/a/c.md": "c", "issue-matrix.json": "{}", "decisions.events.jsonl": ""},
    )
    alias_dir = repo / KITTY_SPECS_DIR / _ALIAS_DIR

    alias = _alias_files(repo)

    assert alias is not None
    assert alias.directory == alias_dir
    assert alias.primary_directory == repo / KITTY_SPECS_DIR / _ALIAS_SLUG
    assert alias.files == tuple(
        alias_dir / name for name in ("decisions.events.jsonl", "issue-matrix.json", "status.events.jsonl", "status.json", "traces/a/c.md", "traces/b.md")
    )


def test_alias_files_never_returns_a_file_that_is_not_a_coordination_kind(tmp_path: Path) -> None:
    repo = _alias_main_repo(tmp_path, files={"status.json": "{}", "spec.md": "s", "src/x.py": "x", "notes.md": "n", "tasks/WP01.md": "w", "plan.md": "p"})
    alias_dir = repo / KITTY_SPECS_DIR / _ALIAS_DIR

    alias = _alias_files(repo)

    assert alias is not None and alias.files == (alias_dir / "status.json",)


def test_alias_files_skips_a_coordination_file_that_is_untracked(tmp_path: Path) -> None:
    repo = _alias_main_repo(tmp_path, files={"status.json": "{}"})
    (repo / KITTY_SPECS_DIR / _ALIAS_DIR / "traces").mkdir()
    (repo / KITTY_SPECS_DIR / _ALIAS_DIR / "traces" / "scratch.md").write_text("mine", encoding="utf-8")

    alias = _alias_files(repo)

    assert alias is not None and alias.files == (repo / KITTY_SPECS_DIR / _ALIAS_DIR / "status.json",)


def test_alias_files_skips_a_tracked_file_already_gone_from_disk(tmp_path: Path) -> None:
    repo = _alias_main_repo(tmp_path, files={"status.json": "{}", "traces/t.md": "t"})
    (repo / KITTY_SPECS_DIR / _ALIAS_DIR / "traces" / "t.md").unlink()

    alias = _alias_files(repo)

    assert alias is not None and [path.name for path in alias.files] == ["status.json"]


def test_alias_files_is_none_when_no_coordination_file_is_tracked(tmp_path: Path) -> None:
    repo = _alias_main_repo(tmp_path, files={"spec.md": "s"})

    assert _alias_files(repo) is None


def test_alias_files_is_none_when_the_status_directory_has_the_primary_name(tmp_path: Path) -> None:
    repo = _alias_main_repo(tmp_path, files={"status.json": "{}"})

    assert _alias_files(repo, _ALIAS_SLUG) is None


def test_alias_files_is_none_for_a_mission_whose_primary_directory_is_the_composed_name(tmp_path: Path) -> None:
    repo = _alias_main_repo(tmp_path, with_primary_dir=False, files={"status.json": "{}", "traces/t.md": "t"})

    assert _alias_files(repo, slug=_ALIAS_DIR) is None


def test_alias_files_is_none_outside_a_coordination_worktree(tmp_path: Path) -> None:
    repo = _alias_main_repo(tmp_path, files={"status.json": "{}"})

    alias = bp.coordination_alias_files(main_repo=repo, mission_slug=_ALIAS_SLUG, status_feature_dir=repo / KITTY_SPECS_DIR / _ALIAS_DIR)

    assert alias is None


def test_alias_files_refuses_an_unsafe_directory_name(tmp_path: Path) -> None:
    repo = _alias_main_repo(tmp_path)

    with pytest.raises(ValueError):
        _alias_files(repo, "..hidden")


def _write_log(path: Path, *lines: str) -> Path:
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    return path


def test_alias_events_preserved_accepts_a_subset_and_ignores_blank_lines(tmp_path: Path) -> None:
    alias = _write_log(tmp_path / "alias.jsonl", '{"event_id": "A"}', "", '{"event_id": "B"}')
    primary = _write_log(tmp_path / "primary.jsonl", '{"event_id": "A"}', '{"event_id": "B"}', '{"event_id": "C"}')

    bp.assert_alias_events_preserved(alias_events_path=alias, primary_events_path=primary)


def test_alias_events_preserved_names_the_missing_event(tmp_path: Path) -> None:
    alias = _write_log(tmp_path / "alias.jsonl", '{"event_id": "A"}', '{"event_id": "LOST"}')
    primary = _write_log(tmp_path / "primary.jsonl", '{"event_id": "A"}')

    with pytest.raises(bp.AliasStatusEventsNotPreserved, match="LOST"):
        bp.assert_alias_events_preserved(alias_events_path=alias, primary_events_path=primary)


@pytest.mark.parametrize("bad_line", ["{not json", '{"wp_id": "WP01"}', '{"event_id": 7}', "[1, 2]"])
def test_alias_events_preserved_fails_closed_on_a_line_without_a_string_event_id(tmp_path: Path, bad_line: str) -> None:
    alias = _write_log(tmp_path / "alias.jsonl", bad_line)
    primary = _write_log(tmp_path / "primary.jsonl", '{"event_id": "A"}')

    with pytest.raises(bp.AliasStatusEventsNotPreserved):
        bp.assert_alias_events_preserved(alias_events_path=alias, primary_events_path=primary)


def test_alias_events_refusal_text_names_the_mission_the_directory_the_ids_and_the_code(tmp_path: Path) -> None:
    (tmp_path / "kitty-specs" / "m-01KX0000").mkdir(parents=True)
    alias = _write_log(tmp_path / "kitty-specs" / "m-01KX0000" / "status.events.jsonl", '{"event_id": "A"}', '{"event_id": "LOST"}')
    primary = _write_log(tmp_path / "primary.jsonl", '{"event_id": "A"}')

    with pytest.raises(bp.AliasStatusEventsNotPreserved) as raised:
        bp.assert_alias_events_preserved(alias_events_path=alias, primary_events_path=primary)

    text = raised.value.refusal_text("m")
    assert text.startswith("Mission m: ")
    assert "kitty-specs/m-01KX0000" in text
    assert "LOST" in text
    assert "the primary Mission directory's event log lacks: LOST" in text
    assert "merged primary log" not in text  # terminology canon: never bare "primary"
    assert text.endswith("Error code: ALIAS_STATUS_EVENTS_NOT_PRESERVED.")


def test_alias_events_refusal_text_for_an_unreadable_log_carries_the_reason_not_an_id_list(tmp_path: Path) -> None:
    (tmp_path / "kitty-specs" / "m-01KX0000").mkdir(parents=True)
    alias = _write_log(tmp_path / "kitty-specs" / "m-01KX0000" / "status.events.jsonl", "{not json")
    primary = _write_log(tmp_path / "primary.jsonl", '{"event_id": "A"}')

    with pytest.raises(bp.AliasStatusEventsNotPreserved) as raised:
        bp.assert_alias_events_preserved(alias_events_path=alias, primary_events_path=primary)

    text = raised.value.refusal_text("m")
    assert "cannot be proven present in the primary Mission directory's event log" in text
    assert "merged primary log" not in text
    assert "is not an event with an event_id" in text
    assert text.endswith("Error code: ALIAS_STATUS_EVENTS_NOT_PRESERVED.")
