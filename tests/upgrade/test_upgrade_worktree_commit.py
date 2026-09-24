"""Upgrade-worktree coherence: the runner commits each checkout it touches (#2392).

`spec-kitty upgrade` applies migrations across sibling worktrees but
historically committed only the main checkout, leaving worktrees dirty — which
then blocked `spec-kitty merge` (the #1826/NFR-002 guard refuses to advance a
branch whose worktree has uncommitted changes). These tests pin the canonical
seam fix (epic #2392):

* #2385 — ``MigrationRunner._upgrade_worktrees`` auto-commits each worktree's
  new churn on that worktree's own branch, with a per-worktree baseline
  protecting pre-existing uncommitted work.
* #1873 — freshly synthesized worktree metadata is persisted (and committed)
  even when the detected version already equals the target.
* Invariant (Slice C): after an upgrade run, every touched checkout has no
  porcelain diff beyond what was already dirty before the run.
"""

from __future__ import annotations

import subprocess
import shutil
from collections import deque
from pathlib import Path

import pytest
import yaml

from specify_cli.migration.schema_version import REQUIRED_SCHEMA_VERSION
from specify_cli.upgrade.migrations.base import BaseMigration, MigrationResult
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.runner import MigrationRunner

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_METADATA_YAML = (
    "spec_kitty:\n"
    "  version: '{version}'\n"
    "  initialized_at: '2026-01-01T00:00:00'\n"
    "environment:\n"
    "  python_version: '3.12'\n"
    "  platform: linux\n"
    "  platform_version: ''\n"
    "migrations:\n"
    "  applied: []\n"
)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _git_out(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _init_repo(root: Path, version: str = "3.2.1") -> None:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "README.md").write_text("# repo\n", encoding="utf-8")
    # Real spec-kitty projects gitignore the execution worktrees.
    (root / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    (root / ".kittify").mkdir()
    (root / ".kittify" / "metadata.yaml").write_text(_METADATA_YAML.format(version=version), encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")


def _add_worktree(root: Path, name: str, branch: str) -> Path:
    wt = root / ".worktrees" / name
    _git(root, "worktree", "add", "-q", "-b", branch, str(wt))
    return wt


def _dirty(wt: Path) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(wt), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [ln for ln in out.stdout.splitlines() if ln.strip()]


def test_worktree_upgrade_churn_is_committed_on_its_own_branch(tmp_path: Path) -> None:
    """#2385: the runner commits worktree upgrade churn; the tree ends clean."""
    root = tmp_path / "repo"
    _init_repo(root)
    wt = _add_worktree(root, "m-lane-a", "kitty/mission-m-lane-a")

    result = MigrationRunner(root)._upgrade_worktrees("3.2.9", [], dry_run=False, auto_commit=True)

    assert result["errors"] == []
    assert not any("auto-commit" in w.lower() for w in result["warnings"]), result["warnings"]
    assert _dirty(wt) == [], "worktree must be clean (churn committed) after upgrade"
    # The commit landed on the worktree's own branch.
    assert _git_out(wt, "branch", "--show-current") == "kitty/mission-m-lane-a"
    assert "spec-kitty upgrade" in _git_out(wt, "log", "-1", "--pretty=%s")
    # And main's branch did NOT receive the worktree commit.
    assert "spec-kitty upgrade" not in _git_out(root, "log", "-1", "--pretty=%s")


def test_preexisting_uncommitted_work_in_worktree_is_not_committed(tmp_path: Path) -> None:
    """#2385 baseline: in-flight WP edits are never swept into the upgrade commit."""
    root = tmp_path / "repo"
    _init_repo(root)
    wt = _add_worktree(root, "m-lane-b", "kitty/mission-m-lane-b")

    # Pre-existing uncommitted work exists BEFORE the upgrade runs.
    (wt / "kitty-specs").mkdir()
    (wt / "kitty-specs" / "wip.md").write_text("wip\n", encoding="utf-8")
    (wt / "README.md").write_text("# repo (edited in lane)\n", encoding="utf-8")

    MigrationRunner(root)._upgrade_worktrees("3.2.9", [], dry_run=False, auto_commit=True)

    remaining = _dirty(wt)
    # Untracked dirs are reported as a single `?? kitty-specs/` entry.
    assert any("kitty-specs" in ln for ln in remaining), remaining
    assert any("README.md" in ln for ln in remaining), remaining
    assert not any("metadata.yaml" in ln for ln in remaining), remaining


def test_synthesized_worktree_metadata_is_saved_when_version_matches_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#1873: metadata synthesized from None must be persisted (and committed)
    even when the detected version already equals the target."""
    root = tmp_path / "repo"
    _init_repo(root)
    wt = _add_worktree(root, "m-lane-c", "kitty/mission-m-lane-c")

    # The worktree has a .kittify dir but no metadata.yaml (the self-healing
    # scenario from #1857), and its detected version already equals the target.
    (wt / ".kittify" / "metadata.yaml").unlink()
    _git(wt, "commit", "-q", "-am", "drop worktree metadata")

    class _StubDetector:
        def __init__(self, _path: Path) -> None:
            pass

        def detect_version(self) -> str:
            return "3.2.9"

    monkeypatch.setattr("specify_cli.upgrade.runner.VersionDetector", _StubDetector)

    MigrationRunner(root)._upgrade_worktrees("3.2.9", [], dry_run=False, auto_commit=True)

    assert (wt / ".kittify" / "metadata.yaml").exists(), "synthesized worktree metadata must be saved to disk (#1873)"
    assert _dirty(wt) == [], "the healed metadata must also be committed"
    assert "spec-kitty upgrade" in _git_out(wt, "log", "-1", "--pretty=%s"), "synthesized metadata commit must land on the worktree branch (#1873)"


def test_genuine_worktree_migration_still_mints_fresh_stamp_not_main_aligned(tmp_path: Path) -> None:
    """#4972 scope guard (no #2385 regression): a worktree whose migration
    applied REAL content must still mint its own fresh ``now_utc()`` stamp
    and commit -- the #4972 main-aligned bookkeeping-only path must never
    swallow a genuine change, even when main's own stamp is stale/distinct.
    """
    root = tmp_path / "repo"
    _init_repo(root, version="3.2.1")
    # The worktree forks BEFORE main's later bump, so it starts stale (no
    # `last_upgraded_at` yet, old version) -- mirroring the real trigger.
    wt = _add_worktree(root, "m-lane-genuine", "kitty/mission-m-lane-genuine")

    old_main_stamp = "2020-01-01T00:00:00+00:00"
    (root / ".kittify" / "metadata.yaml").write_text(
        "spec_kitty:\n"
        "  version: '3.2.9'\n"
        "  initialized_at: '2026-01-01T00:00:00'\n"
        f"  last_upgraded_at: '{old_main_stamp}'\n"
        "environment:\n"
        "  python_version: '3.12'\n"
        "  platform: linux\n"
        "  platform_version: ''\n"
        "migrations:\n"
        "  applied: []\n",
        encoding="utf-8",
    )
    _git(root, "commit", "-q", "-am", "bump main metadata fixture")

    MigrationRegistry.clear()

    @MigrationRegistry.register
    class _GenuineChangeStub(BaseMigration):
        migration_id = "test_4972_genuine_change_stub"
        description = "T003 stub -- real worktree content change"
        target_version = "3.2.9"
        runs_on_worktrees = True

        def detect(self, project_path: Path) -> bool:  # noqa: ARG002
            return True

        def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002
            return True, ""

        def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
            if not dry_run:
                (project_path / "genuine-change.txt").write_text("real content\n", encoding="utf-8")
            return MigrationResult(success=True, changes_made=["wrote genuine-change.txt"])

    try:
        result = MigrationRunner(root)._upgrade_worktrees("3.2.9", [_GenuineChangeStub()], dry_run=False, auto_commit=True)
        assert result["errors"] == []

        wt_data = yaml.safe_load((wt / ".kittify" / "metadata.yaml").read_text(encoding="utf-8-sig"))
        wt_stamp = wt_data["spec_kitty"]["last_upgraded_at"]
        assert wt_stamp != old_main_stamp, (
            "a genuine worktree migration must mint its own fresh stamp, never align to main's stale value (#2385, no #4972 regression)"
        )
        assert wt_data["spec_kitty"]["version"] == "3.2.9"
        assert (wt / "genuine-change.txt").exists()
        assert _dirty(wt) == []
        assert "spec-kitty upgrade" in _git_out(wt, "log", "-1", "--pretty=%s")
    finally:
        MigrationRegistry.clear()


def test_current_equals_target_worktree_catchup_ends_byte_identical_to_main(tmp_path: Path) -> None:
    """#4972 T004: the teammate-first-run path -- main is already at
    ``target_version`` (unchanged by this call) and a live worktree is
    merely lagging on ``version`` -- must leave the worktree's
    ``.kittify/metadata.yaml`` byte-identical to main's, sharing the same
    ``last_upgraded_at`` rather than minting a fresh one.
    """
    root = tmp_path / "repo"
    _init_repo(root, version="3.2.1")
    main_stamp = "2026-03-01T12:00:00+00:00"
    # Main's fixture already carries REQUIRED_SCHEMA_VERSION (a real upgrade
    # run stamps it there before ever reaching `_upgrade_worktrees`), so the
    # byte-identical comparison below is a fair like-for-like check.
    schema_version_line = f"  schema_version: {REQUIRED_SCHEMA_VERSION}\n" if REQUIRED_SCHEMA_VERSION is not None else ""
    main_metadata_text = (
        "spec_kitty:\n"
        "  version: '3.2.9'\n"
        "  initialized_at: '2026-01-01T00:00:00'\n"
        f"  last_upgraded_at: '{main_stamp}'\n"
        f"{schema_version_line}"
        "environment:\n"
        "  python_version: '3.12'\n"
        "  platform: linux\n"
        "  platform_version: ''\n"
        "migrations:\n"
        "  applied: []\n"
    )
    (root / ".kittify" / "metadata.yaml").write_text(main_metadata_text, encoding="utf-8")
    _git(root, "commit", "-q", "-am", "main already at target")

    # The worktree lags: it still shows the pre-upgrade version.
    wt = _add_worktree(root, "m-lane-teammate", "kitty/mission-m-lane-teammate")
    wt_metadata_text = (
        "spec_kitty:\n"
        "  version: '3.2.1'\n"
        "  initialized_at: '2026-01-01T00:00:00'\n"
        "environment:\n"
        "  python_version: '3.12'\n"
        "  platform: linux\n"
        "  platform_version: ''\n"
        "migrations:\n"
        "  applied: []\n"
    )
    (wt / ".kittify" / "metadata.yaml").write_text(wt_metadata_text, encoding="utf-8")
    _git(wt, "commit", "-q", "-am", "lagging worktree metadata")

    # current_version == target_version: this mirrors upgrade.py:822's guard
    # (no-migrations, already-current main) funneling into the shared
    # `_upgrade_worktrees` call with an empty migrations list.
    result = MigrationRunner(root)._upgrade_worktrees("3.2.9", [], dry_run=False, auto_commit=True)
    assert result["errors"] == []

    main_data = yaml.safe_load((root / ".kittify" / "metadata.yaml").read_text(encoding="utf-8-sig"))
    wt_data = yaml.safe_load((wt / ".kittify" / "metadata.yaml").read_text(encoding="utf-8-sig"))

    assert wt_data["spec_kitty"]["last_upgraded_at"] == main_stamp
    assert wt_data["spec_kitty"]["version"] == "3.2.9"
    assert wt_data == main_data, "worktree metadata.yaml must end byte-identical to main's (#4972)"


def test_dry_run_writes_and_commits_nothing_in_worktrees(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _init_repo(root)
    wt = _add_worktree(root, "m-lane-d", "kitty/mission-m-lane-d")
    head_before = _git_out(wt, "rev-parse", "HEAD")

    MigrationRunner(root)._upgrade_worktrees("3.2.9", [], dry_run=True, auto_commit=True)

    assert _dirty(wt) == []
    assert _git_out(wt, "rev-parse", "HEAD") == head_before


def test_upgrade_invariant_every_touched_checkout_ends_clean(tmp_path: Path) -> None:
    """Slice C invariant (#2392): after `runner.upgrade(..., auto_commit=True)`,
    no checkout the run touched has porcelain dirt beyond what pre-existed.

    Note: the runner deliberately leaves the main checkout's commit to the CLI
    (`commit_touched_checkout` in upgrade.py). The invariant here covers worktrees
    only; main's remaining dirt is the upgrade churn the CLI will commit on return.

    A stub migration with `runs_on_worktrees=True` is registered so that
    `_upgrade_worktrees` is actually invoked on the `runner.upgrade()` path.
    Without it, the no-migration branch skips `_upgrade_worktrees` when
    `from_version != target_version`, making the test vacuous.
    """
    root = tmp_path / "repo"
    _init_repo(root)
    wt = _add_worktree(root, "m-lane-e", "kitty/mission-m-lane-e")

    # Pre-existing dirt in the lane worktree (must survive uncommitted).
    (wt / "kitty-specs").mkdir()
    (wt / "kitty-specs" / "wip.md").write_text("wip\n", encoding="utf-8")

    # Register a stub migration so the migrations path is taken and
    # _upgrade_worktrees is called. Clear first to prevent order-fragility.
    MigrationRegistry.clear()

    @MigrationRegistry.register
    class _InvariantStubMigration(BaseMigration):
        migration_id = "test_invariant_stub_3_2_9"
        description = "Invariant-test stub — never runs outside this test"
        target_version = "3.2.9"

        def detect(self, project_path: Path) -> bool:
            return not (project_path / ".kittify" / ".invariant-stub").exists()

        def can_apply(self, project_path: Path) -> tuple[bool, str]:
            return True, ""

        def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
            if not dry_run:
                (project_path / ".kittify").mkdir(exist_ok=True)
                (project_path / ".kittify" / ".invariant-stub").write_text("1", encoding="utf-8")
            return MigrationResult(success=True, changes_made=["wrote .kittify/.invariant-stub"])

    try:
        result = MigrationRunner(root).upgrade("3.2.9", dry_run=False, auto_commit=True)
        assert result.success, result.errors

        # Worktree: only the pre-existing WIP dir survives uncommitted.
        assert [ln for ln in _dirty(wt) if "kitty-specs" not in ln] == []
        # Main: runner leaves it for the CLI commit seam — remaining dirt must be
        # upgrade churn only (.kittify/* writes), never pre-existing files.
        main_dirt = _dirty(root)
        assert all(".kittify/" in ln or ".gitignore" in ln for ln in main_dirt), main_dirt
    finally:
        MigrationRegistry.clear()


def test_root_files_written_by_the_run_land_in_the_upgrade_commit(tmp_path: Path) -> None:
    """#2491/#2492 follow-up: root-level files the run writes end in the one
    auto-commit, in the main checkout AND in a worktree, while pre-existing
    operator dirt at the root survives uncommitted.

    Real git, real ``commit_touched_checkout`` — no fakes in the path. This
    pins the class a depth-based root filter kept breaking: ``.gitattributes``
    (merge-driver migrations, which also run in worktrees and tripped the
    ``spec-kitty merge`` dirty guard), ``.claudeignore``
    (``m_3_2_8_provision_kitty_env``) and ``AGENTS.md`` (surface repair).
    """
    from specify_cli.upgrade import autocommit

    root = tmp_path / "repo"
    _init_repo(root)
    (root / ".gitattributes").write_text("*.jsonl merge=union\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "track .gitattributes")
    wt = _add_worktree(root, "m-root-files", "kitty/mission-m-root-files")

    # Pre-existing operator dirt at the root, in both checkouts — must survive.
    (root / "README.md").write_text("# repo (operator edit in flight)\n", encoding="utf-8")
    (wt / "README.md").write_text("# repo (lane edit in flight)\n", encoding="utf-8")

    main_baseline = autocommit.git_status_paths(root)
    wt_baseline = autocommit.git_status_paths(wt)
    assert main_baseline == {"README.md"} and wt_baseline == {"README.md"}

    # "The run": root-level writes of the kinds upgrade actually performs.
    for checkout in (root, wt):
        with (checkout / ".gitattributes").open("a", encoding="utf-8") as handle:
            handle.write("kitty-specs/**/events.jsonl merge=spec-kitty-event-log\n")
    (root / ".claudeignore").write_text(".kittify/.env\n", encoding="utf-8")
    (root / "AGENTS.md").write_text("# Spec Kitty orientation\n", encoding="utf-8")
    (root / ".kittify" / "metadata.yaml").write_text(_METADATA_YAML.format(version="3.2.6"), encoding="utf-8")

    committed, paths, warning = autocommit.commit_touched_checkout(root, main_baseline, "3.2.5", "3.2.6")
    assert (committed, warning) == (True, None)
    assert set(paths) == {".gitattributes", ".claudeignore", "AGENTS.md", ".kittify/metadata.yaml"}
    assert _dirty(root) == [" M README.md"]
    assert set(_git_out(root, "show", "--name-only", "--format=", "HEAD").splitlines()) == set(paths)

    wt_committed, wt_paths, wt_warning = autocommit.commit_touched_checkout(wt, wt_baseline, "3.2.5", "3.2.6")
    assert (wt_committed, wt_paths, wt_warning) == (True, [".gitattributes"], None)
    assert _dirty(wt) == [" M README.md"]


def test_upgrade_commit_preserves_both_sides_of_a_run_rename(tmp_path: Path) -> None:
    """A run-created rename must commit its source deletion and destination.

    Parser-only coverage is insufficient: ``safe_commit`` stages exactly the
    supplied path set, so dropping the porcelain source path can otherwise
    report success after committing only the destination and leaving the
    source deletion staged.
    """
    from specify_cli.upgrade import autocommit

    root = tmp_path / "repo"
    _init_repo(root)
    (root / "old.py").write_text("print('tracked')\n", encoding="utf-8")
    _git(root, "add", "old.py")
    _git(root, "commit", "-q", "-m", "track old path")

    baseline = autocommit.capture_upgrade_baseline(root)
    assert baseline == set()
    _git(root, "mv", "old.py", "new.py")

    committed, paths, warning = autocommit.commit_touched_checkout(root, baseline, "3.2.5", "3.2.6")

    assert (committed, warning) == (True, None)
    assert set(paths) == {"old.py", "new.py"}
    assert _dirty(root) == []
    assert not (root / "old.py").exists()
    assert (root / "new.py").read_text(encoding="utf-8") == "print('tracked')\n"
    assert _git_out(root, "ls-tree", "--name-only", "HEAD", "old.py") == ""
    assert _git_out(root, "ls-tree", "--name-only", "HEAD", "new.py") == "new.py"


def test_upgrade_commit_does_not_sweep_dirty_source_through_rename(tmp_path: Path) -> None:
    """Pre-run operator dirt taints the destination when the run renames it."""
    from specify_cli.upgrade import autocommit

    root = tmp_path / "repo"
    _init_repo(root)
    (root / "old.py").write_text("original\n", encoding="utf-8")
    _git(root, "add", "old.py")
    _git(root, "commit", "-q", "-m", "track old path")

    (root / "old.py").write_text("operator edit\n", encoding="utf-8")
    baseline = autocommit.capture_upgrade_baseline(root)
    assert baseline == {"old.py"}
    _git(root, "mv", "old.py", "new.py")

    committed, paths, warning = autocommit.commit_touched_checkout(root, baseline, "3.2.5", "3.2.6")

    assert (committed, paths, warning) == (False, [], None)
    assert _dirty(root), "the operator-owned rename must remain for manual review"
    assert _git_out(root, "show", "HEAD:old.py") == "original"
    assert (root / "new.py").read_text(encoding="utf-8") == "operator edit\n"


def test_upgrade_commit_does_not_sweep_dirty_source_through_filesystem_move(
    tmp_path: Path,
) -> None:
    """Production migrations use filesystem moves, which porcelain splits."""
    from specify_cli.upgrade import autocommit

    root = tmp_path / "repo"
    _init_repo(root)
    (root / "old.py").write_text("original\n", encoding="utf-8")
    _git(root, "add", "old.py")
    _git(root, "commit", "-q", "-m", "track old path")

    (root / "old.py").write_text("operator edit\n", encoding="utf-8")
    baseline = autocommit.capture_upgrade_baseline(root)
    assert baseline == {"old.py"}
    (root / "old.py").rename(root / "new.py")

    committed, paths, warning = autocommit.commit_touched_checkout(root, baseline, "3.2.5", "3.2.6")

    assert (committed, paths, warning) == (False, [], None)
    assert _dirty(root), "the operator-owned filesystem move must remain for review"
    assert _git_out(root, "show", "HEAD:old.py") == "original"
    assert (root / "new.py").read_text(encoding="utf-8") == "operator edit\n"


def test_upgrade_commit_does_not_sweep_copy_of_dirty_source(tmp_path: Path) -> None:
    """Run-local copy provenance taints a copy porcelain cannot relate."""
    from specify_cli.upgrade import autocommit

    root = tmp_path / "repo"
    _init_repo(root)
    (root / "old.py").write_text("original\n", encoding="utf-8")
    _git(root, "add", "old.py")
    _git(root, "commit", "-q", "-m", "track old path")

    (root / "old.py").write_text("operator edit\n", encoding="utf-8")
    baseline = autocommit.capture_upgrade_baseline(root)
    assert baseline == {"old.py"}
    shutil.copy2(root / "old.py", root / "new.py")

    committed, paths, warning = autocommit.commit_touched_checkout(root, baseline, "3.2.5", "3.2.6")

    assert (committed, paths, warning) == (False, [], None)
    assert set(_dirty(root)) == {" M old.py", "?? new.py"}
    assert _git_out(root, "show", "HEAD:old.py") == "original"


def test_upgrade_commit_fails_closed_when_mutation_journal_overflows(tmp_path: Path, monkeypatch) -> None:
    """A baseline older than retained provenance must never auto-commit."""
    from specify_cli.upgrade import autocommit

    root = tmp_path / "repo"
    _init_repo(root)
    old_path = root / "old.py"
    old_path.write_text("original\n", encoding="utf-8")
    _git(root, "add", "old.py")
    _git(root, "commit", "-q", "-m", "track old path")

    monkeypatch.setattr(autocommit, "_MUTATION_EVENTS", deque(maxlen=2))
    monkeypatch.setattr(autocommit, "_MUTATION_DROPPED_THROUGH", 0)
    old_path.write_text("operator edit\n", encoding="utf-8")
    baseline = autocommit.capture_upgrade_baseline(root)
    shutil.copy2(old_path, root / "new.py")
    for index in range(2):
        autocommit.record_upgrade_mutation(
            tmp_path / f"irrelevant-{index}",
            tmp_path / f"irrelevant-copy-{index}",
            is_move=False,
        )

    committed, paths, warning = autocommit.commit_touched_checkout(root, baseline, "3.2.5", "3.2.6")

    assert (committed, paths, warning) == (False, [], autocommit.UPGRADE_COMMIT_SKIP_WARNING)
    assert set(_dirty(root)) == {" M old.py", "?? new.py"}


def test_upgrade_commit_keeps_unrelated_identical_run_write_eligible(tmp_path: Path) -> None:
    """Content equality alone is not ownership or copy provenance."""
    from specify_cli.upgrade import autocommit

    root = tmp_path / "repo"
    _init_repo(root)
    operator_dir = root / "operator"
    operator_dir.mkdir()
    (operator_dir / "note.txt").write_text("same-content\n", encoding="utf-8")
    baseline = autocommit.capture_upgrade_baseline(root)
    assert baseline == {"operator/note.txt"}

    run_file = root / ".agents" / "skills" / "run-written.txt"
    run_file.parent.mkdir(parents=True)
    run_file.write_text("same-content\n", encoding="utf-8")

    committed, paths, warning = autocommit.commit_touched_checkout(root, baseline, "3.2.5", "3.2.6")

    assert (committed, paths, warning) == (True, [".agents/skills/run-written.txt"], None)
    assert _dirty(root) == ["?? operator/"]


def test_upgrade_commit_taints_explicit_transformed_relocation(tmp_path: Path) -> None:
    """Manual read/write/unlink relocations declare provenance explicitly."""
    from specify_cli.upgrade import autocommit

    root = tmp_path / "repo"
    _init_repo(root)
    old_path = root / "old.md"
    new_path = root / "new.md"
    old_path.write_text("original\n", encoding="utf-8")
    _git(root, "add", "old.md")
    _git(root, "commit", "-q", "-m", "track old path")

    old_path.write_text("operator edit\n", encoding="utf-8")
    baseline = autocommit.capture_upgrade_baseline(root)
    assert baseline == {"old.md"}
    autocommit.record_upgrade_mutation(old_path, new_path, is_move=True)
    new_path.write_text(old_path.read_text(encoding="utf-8") + "migration rewrite\n", encoding="utf-8")
    old_path.unlink()

    committed, paths, warning = autocommit.commit_touched_checkout(root, baseline, "3.2.5", "3.2.6")

    assert (committed, paths, warning) == (False, [], None)
    assert _dirty(root), "transformed operator content must remain for manual review"


def test_legacy_lane_migration_preserves_dirty_source_ownership(tmp_path: Path) -> None:
    """The production 0.9.0 rewrite declares its transformed move provenance."""
    from specify_cli.upgrade import autocommit
    from specify_cli.upgrade.migrations.m_0_9_0_frontmatter_only_lanes import (
        FrontmatterOnlyLanesMigration,
    )

    root = tmp_path / "repo"
    _init_repo(root)
    source = root / "kitty-specs" / "001-feature" / "tasks" / "planned" / "WP01.md"
    source.parent.mkdir(parents=True)
    source.write_text("---\ntitle: Original\n---\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "track legacy lane")

    source.write_text("---\ntitle: Operator edit\n---\n", encoding="utf-8")
    baseline = autocommit.capture_upgrade_baseline(root)
    result = FrontmatterOnlyLanesMigration().apply(root)
    assert result.success

    committed, paths, warning = autocommit.commit_touched_checkout(root, baseline, "0.8.0", "0.9.0")

    assert (committed, paths, warning) == (False, [], None)
    assert _dirty(root), "the transformed operator edit must remain for review"


def test_upgrade_commit_detects_new_file_beneath_preexisting_untracked_directory(
    tmp_path: Path,
) -> None:
    """Per-file porcelain keeps new churn visible under operator-owned dirs."""
    from specify_cli.upgrade import autocommit

    root = tmp_path / "repo"
    _init_repo(root)
    skill_dir = root / ".agents" / "skills"
    skill_dir.mkdir(parents=True)
    operator_file = skill_dir / "operator.txt"
    operator_file.write_text("operator-owned\n", encoding="utf-8")

    baseline = autocommit.git_status_paths(root)
    assert baseline == {".agents/skills/operator.txt"}
    run_file = skill_dir / "run-written.txt"
    run_file.write_text("upgrade-owned\n", encoding="utf-8")

    committed, paths, warning = autocommit.commit_touched_checkout(root, baseline, "3.2.5", "3.2.6")

    assert (committed, warning) == (True, None)
    assert paths == [".agents/skills/run-written.txt"]
    assert _dirty(root) == ["?? .agents/skills/operator.txt"]
    assert _git_out(root, "show", "HEAD:.agents/skills/run-written.txt") == "upgrade-owned"
    assert _git_out(root, "ls-tree", "--name-only", "HEAD", ".agents/skills/operator.txt") == ""


def test_upgrade_commit_preserves_trailing_space_path_identity(tmp_path: Path) -> None:
    """A run-created spaced path must not alias pre-run operator dirt."""
    from specify_cli.upgrade import autocommit

    root = tmp_path / "repo"
    _init_repo(root)
    (root / "README.md").write_text("operator edit\n", encoding="utf-8")
    baseline = autocommit.git_status_paths(root)
    assert baseline == {"README.md"}

    spaced_path = "README.md "
    (root / spaced_path).write_text("upgrade-owned\n", encoding="utf-8")

    committed, paths, warning = autocommit.commit_touched_checkout(root, baseline, "3.2.5", "3.2.6")

    assert (committed, paths, warning) == (True, [spaced_path], None)
    assert _dirty(root) == [" M README.md"]
    assert _git_out(root, "show", "HEAD:README.md") == "# repo"
    assert _git_out(root, "show", f"HEAD:{spaced_path}") == "upgrade-owned"
