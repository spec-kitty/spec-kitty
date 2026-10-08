"""Work-package frontmatter writers run under the Mission write lock (mission-writer-followups WP04, US2).

Each overlap test pauses writer A just before it writes the work-package file (an injected pause point, not a
sleep: ``tests/_meta_overlap.py``), lets writer B run on another thread, and releases A once B finished or was
observed waiting for the lock. Without the lock A writes its stale copy over B's change; with it B queues
behind A and both changes survive.

The finalize tests cover its long in-memory window (it reads every work package long before it flushes) and the
compare-and-swap restore of its write scope (plan A8, A9).
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

import specify_cli.frontmatter as frontmatter_module
from kernel.atomic import atomic_write
from specify_cli.cli.commands.agent.finalize_status_surface import StatusSurfaceGuard
from specify_cli.cli.commands.agent import mission_finalize_bootstrap as bootstrap
from specify_cli.cli.commands.agent import mission_finalize_commit as finalize_commit
from specify_cli.cli.commands.agent.tasks import app as tasks_app
from specify_cli.frontmatter import read_frontmatter, write_frontmatter
from specify_cli.status.locking import feature_status_lock_path, holds_status_lock
from tests._meta_overlap import run_overlap

pytestmark = [pytest.mark.unit]

SLUG = "060-test"
MID8 = "01COORD0"
COORD_NAME = f"{SLUG}-{MID8}"
WP_ID = "WP01"
BODY = "\n# WP01\n\n  indented line  \n\ttabbed\n\nUnicode: éè ✓\n\nlast line, no trailing newline"
SPEC_CONTENT = """\
# Spec
## Functional Requirements
| ID | Requirement | Acceptance Criteria | Status |
| --- | --- | --- | --- |
| FR-001 | First requirement | Done | proposed |
| FR-002 | Second requirement | Done | proposed |
"""


def _is_wp_file(path: Path) -> bool:
    return path.name.startswith("WP") and path.suffix == ".md"


def _overlap(monkeypatch: pytest.MonkeyPatch, writer_a: Any, writer_b: Any) -> list[Exception]:
    return run_overlap(monkeypatch, writer_a, writer_b, pause_when=_is_wp_file, atomic_modules=(frontmatter_module,))


@pytest.fixture
def mission(tmp_path: Path) -> tuple[Path, Path, Path]:
    """``(repo, primary_dir, wp_file)`` for a legacy bare-directory coordination Mission (primary ``060-test``)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True, capture_output=True)
    primary = repo / "kitty-specs" / SLUG
    (primary / "tasks").mkdir(parents=True)
    meta = {
        "mission_slug": SLUG,
        "slug": SLUG,
        "mission_type": "software-dev",
        "mission_id": f"{MID8}XXXXXXXXXXXXXXXXXX",
        "mid8": MID8,
        "coordination_branch": f"kitty/mission-{COORD_NAME}",
        "target_branch": "main",
    }
    (primary / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (primary / "spec.md").write_text(SPEC_CONTENT, encoding="utf-8")
    wp_file = primary / "tasks" / f"{WP_ID}-test.md"
    wp_file.write_text(
        "---\n"
        f'work_package_id: "{WP_ID}"\n'
        'title: "Test"\n'
        "dependencies: []\n"
        "execution_mode: code_change\n"
        "owned_files:\n- src/x.py\n"
        "authoritative_surface: src/\n"
        f"---\n{BODY}",
        encoding="utf-8",
    )
    return repo, primary, wp_file


def _refs(wp_file: Path) -> list[str]:
    frontmatter, _body = read_frontmatter(wp_file)
    return list(frontmatter.get("requirement_refs") or [])


# ---------------------------------------------------------------------------
# locked_update_frontmatter (D2)
# ---------------------------------------------------------------------------


def test_locked_update_frontmatter_preserves_the_body_byte_for_byte(mission: tuple[Path, Path, Path]) -> None:
    from specify_cli.frontmatter import locked_update_frontmatter

    repo, primary, wp_file = mission
    written = locked_update_frontmatter(wp_file, lambda fm: fm.update(requirement_refs=["FR-001"]), feature_dir=primary, repo_root=repo)
    assert written["requirement_refs"] == ["FR-001"]
    _frontmatter, body = read_frontmatter(wp_file)
    assert body == BODY
    assert wp_file.read_text(encoding="utf-8").endswith(f"---\n{BODY}")


def test_locked_update_frontmatter_writes_nothing_when_mutate_returns_false(mission: tuple[Path, Path, Path]) -> None:
    from specify_cli.frontmatter import locked_update_frontmatter

    repo, primary, wp_file = mission
    before = wp_file.read_bytes()
    locked_update_frontmatter(wp_file, lambda fm: False, feature_dir=primary, repo_root=repo)
    assert wp_file.read_bytes() == before


def test_locked_update_frontmatter_holds_the_canonical_mission_lock_while_it_mutates(mission: tuple[Path, Path, Path]) -> None:
    """The primary directory ``060-test`` keys the lock the coordination directory ``060-test-01COORD0`` uses (A1)."""
    from specify_cli.frontmatter import locked_update_frontmatter

    repo, primary, wp_file = mission
    lock_path = feature_status_lock_path(repo, COORD_NAME)
    seen: list[bool] = []

    def mutate(fm: dict[str, Any]) -> None:
        seen.append(holds_status_lock(lock_path))
        fm["requirement_refs"] = ["FR-002"]

    locked_update_frontmatter(wp_file, mutate, feature_dir=primary, repo_root=repo)
    assert seen == [True]
    assert not holds_status_lock(lock_path)


def test_two_locked_frontmatter_writers_both_keep_their_field(monkeypatch: pytest.MonkeyPatch, mission: tuple[Path, Path, Path]) -> None:
    from specify_cli.frontmatter import locked_update_frontmatter

    repo, primary, wp_file = mission
    errors = _overlap(
        monkeypatch,
        lambda: locked_update_frontmatter(wp_file, lambda fm: fm.update(requirement_refs=["FR-001"]), feature_dir=primary, repo_root=repo),
        lambda: locked_update_frontmatter(wp_file, lambda fm: fm.update(branch_strategy="kept"), feature_dir=primary, repo_root=repo),
    )
    assert errors == []
    frontmatter, body = read_frontmatter(wp_file)
    assert frontmatter["requirement_refs"] == ["FR-001"]
    assert frontmatter["branch_strategy"] == "kept"
    assert body == BODY


# ---------------------------------------------------------------------------
# FR-002 / T058: two overlapping ``map-requirements`` invocations keep both refs
# ---------------------------------------------------------------------------


@pytest.fixture
def restore_std_streams() -> Iterator[None]:
    """``CliRunner.invoke`` swaps the process-wide std streams; two threads must not leave them swapped."""
    saved = (sys.stdin, sys.stdout, sys.stderr)
    try:
        yield
    finally:
        sys.stdin, sys.stdout, sys.stderr = saved


def _map_requirements(refs: str) -> int:
    result = CliRunner().invoke(tasks_app, ["map-requirements", "--wp", WP_ID, "--refs", refs, "--no-auto-commit", "--json"])
    return result.exit_code


@pytest.mark.usefixtures("restore_std_streams")
def test_two_overlapping_map_requirements_invocations_keep_both_refs(monkeypatch: pytest.MonkeyPatch, mission: tuple[Path, Path, Path]) -> None:
    repo, _primary, wp_file = mission
    monkeypatch.setenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", "1")
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    exit_codes: dict[str, int] = {}

    def run(name: str, refs: str) -> None:
        exit_codes[name] = _map_requirements(refs)

    with (
        patch("specify_cli.cli.commands.agent.tasks.locate_project_root", Mock(return_value=repo)),
        patch("specify_cli.cli.commands.agent.tasks._find_mission_slug", Mock(return_value=SLUG)),
        patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out", Mock(return_value=(repo, "main"))),
    ):
        errors = _overlap(monkeypatch, lambda: run("a", "FR-001"), lambda: run("b", "FR-002"))

    assert errors == []
    assert exit_codes == {"a": 0, "b": 0}
    assert sorted(_refs(wp_file)) == ["FR-001", "FR-002"]
    assert read_frontmatter(wp_file)[1] == BODY


# ---------------------------------------------------------------------------
# FR-003: the finalize flush applies its delta to the frontmatter and body it reads under the lock
# ---------------------------------------------------------------------------


def _bootstrap_state(repo: Path, wp_file: Path) -> bootstrap._BootstrapState:
    """Finalize's in-memory window: the work package is read now and flushed later."""
    state = bootstrap._BootstrapState()
    contradiction = bootstrap._bootstrap_one_wp(
        wp_file,
        state,
        {WP_ID: []},
        {},
        None,
        SLUG,
        repo,
        "main",
        merge_target_branch=None,
        validate_only=False,
        json_output=True,
    )
    assert contradiction is None
    assert state.pending_writes, "the fixture work package must need a bootstrap write"
    return state


def test_finalize_flush_keeps_a_requirement_ref_a_concurrent_writer_added(mission: tuple[Path, Path, Path]) -> None:
    repo, _primary, wp_file = mission
    state = _bootstrap_state(repo, wp_file)

    frontmatter, body = read_frontmatter(wp_file)  # map-requirements lands after finalize read the work package
    frontmatter["requirement_refs"] = ["FR-001"]
    write_frontmatter(wp_file, frontmatter, body)

    bootstrap._flush_frontmatter_writes(state, validate_only=False)

    flushed, _ = read_frontmatter(wp_file)
    assert flushed["requirement_refs"] == ["FR-001"]
    assert flushed["planning_base_branch"] == "main"  # finalize's own field delta still lands


def test_finalize_flush_keeps_a_body_note_a_concurrent_writer_added(mission: tuple[Path, Path, Path]) -> None:
    repo, _primary, wp_file = mission
    state = _bootstrap_state(repo, wp_file)

    frontmatter, body = read_frontmatter(wp_file)
    note = f"{body}\n\n## Reviewer note\n\nadded after finalize read the file\n"
    write_frontmatter(wp_file, frontmatter, note)

    bootstrap._flush_frontmatter_writes(state, validate_only=False)

    flushed, flushed_body = read_frontmatter(wp_file)
    assert flushed_body == note
    assert flushed["planning_base_branch"] == "main"


def test_finalize_flush_does_not_overwrite_refs_populated_meanwhile_by_its_own_populate_when_empty_rule(
    mission: tuple[Path, Path, Path],
) -> None:
    """``requirement_refs`` is populated only into an empty list (FR-004, #2991): re-judged on the fresh read."""
    repo, _primary, wp_file = mission
    state = bootstrap._BootstrapState()
    bootstrap._bootstrap_one_wp(
        wp_file, state, {WP_ID: []}, {WP_ID: ["FR-002"]}, None, SLUG, repo, "main", merge_target_branch=None, validate_only=False, json_output=True
    )
    frontmatter, body = read_frontmatter(wp_file)
    frontmatter["requirement_refs"] = ["FR-001"]
    write_frontmatter(wp_file, frontmatter, body)

    bootstrap._flush_frontmatter_writes(state, validate_only=False)

    assert _refs(wp_file) == ["FR-001"]


def test_finalize_flush_and_a_locked_writer_overlap_keep_both(monkeypatch: pytest.MonkeyPatch, mission: tuple[Path, Path, Path]) -> None:
    from specify_cli.frontmatter import locked_update_frontmatter

    repo, primary, wp_file = mission
    state = _bootstrap_state(repo, wp_file)
    errors = _overlap(
        monkeypatch,
        lambda: bootstrap._flush_frontmatter_writes(state, validate_only=False),
        lambda: locked_update_frontmatter(wp_file, lambda fm: fm.update(requirement_refs=["FR-001"]), feature_dir=primary, repo_root=repo),
    )
    assert errors == []
    flushed, body = read_frontmatter(wp_file)
    assert flushed["requirement_refs"] == ["FR-001"]
    assert flushed["planning_base_branch"] == "main"
    assert body == BODY


# ---------------------------------------------------------------------------
# A8: the finalize write-scope restore is a compare-and-swap on every branch
# ---------------------------------------------------------------------------


class _LockRecorder:
    """Stands in for ``mission_write_lock`` and records whether the restore ran inside a hold."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.depth = 0
        self.writes_outside_hold: list[str] = []
        real = importlib.import_module(finalize_commit.__name__).mission_write_lock
        recorder = self
        real_write_bytes = Path.write_bytes
        real_unlink = Path.unlink

        from contextlib import contextmanager

        @contextmanager
        def recording_lock(*args: Any, **kwargs: Any) -> Iterator[Path]:
            with real(*args, **kwargs) as held:
                recorder.depth += 1
                try:
                    yield held
                finally:
                    recorder.depth -= 1

        def write_bytes(self_path: Path, data: bytes) -> int:
            if recorder.depth == 0 and self_path.name == "tasks.md":
                recorder.writes_outside_hold.append(str(self_path))
            return real_write_bytes(self_path, data)

        def unlink(self_path: Path, missing_ok: bool = False) -> None:
            if recorder.depth == 0 and self_path.name == "created.md":
                recorder.writes_outside_hold.append(str(self_path))
            real_unlink(self_path, missing_ok=missing_ok)

        monkeypatch.setattr(finalize_commit, "mission_write_lock", recording_lock)
        monkeypatch.setattr(Path, "write_bytes", write_bytes)
        monkeypatch.setattr(Path, "unlink", unlink)


@pytest.fixture
def scope(mission: tuple[Path, Path, Path]) -> tuple[Path, Path]:
    """``(mission_dir, tasks_md)``: a tracked file finalize rewrites."""
    _repo, primary, _wp = mission
    tasks_md = primary / "tasks.md"
    tasks_md.write_text("original\n", encoding="utf-8")
    return primary, tasks_md


@contextmanager
def _finalize_run() -> Iterator[finalize_commit.FinalizeWriteLedger]:
    """A finalize run's write ledger: whatever the block writes through ``atomic_write`` is recorded as finalize's."""
    ledger, ledger_token, observer_token = finalize_commit.begin_write_ledger()
    try:
        yield ledger
    finally:
        finalize_commit.end_write_ledger(ledger_token, observer_token)


def _finalize_writes(path: Path, text: str) -> None:
    atomic_write(path, text)


def test_restore_rewrites_a_file_still_holding_what_finalize_wrote(monkeypatch: pytest.MonkeyPatch, scope: tuple[Path, Path]) -> None:
    mission_dir, tasks_md = scope
    recorder = _LockRecorder(monkeypatch)
    before = finalize_commit._snapshot_mission_write_scope(mission_dir)
    with _finalize_run() as ledger:
        _finalize_writes(tasks_md, "finalize wrote this\n")

    kept = finalize_commit._restore_mission_write_scope(before, mission_dir, written=ledger.written)

    assert tasks_md.read_text(encoding="utf-8") == "original\n"
    assert kept == []
    assert recorder.writes_outside_hold == []


def test_restore_keeps_a_rewritten_file_another_writer_changed(scope: tuple[Path, Path]) -> None:
    mission_dir, tasks_md = scope
    before = finalize_commit._snapshot_mission_write_scope(mission_dir)
    with _finalize_run() as ledger:
        _finalize_writes(tasks_md, "finalize wrote this\n")
    tasks_md.write_text("another writer's edit\n", encoding="utf-8")

    kept = finalize_commit._restore_mission_write_scope(before, mission_dir, written=ledger.written)

    assert tasks_md.read_text(encoding="utf-8") == "another writer's edit\n"
    assert kept == [tasks_md]


def test_restore_deletes_a_file_finalize_created_while_it_is_unchanged(monkeypatch: pytest.MonkeyPatch, scope: tuple[Path, Path]) -> None:
    mission_dir, _tasks_md = scope
    recorder = _LockRecorder(monkeypatch)
    before = finalize_commit._snapshot_mission_write_scope(mission_dir)
    created = mission_dir / "created.md"
    with _finalize_run() as ledger:
        _finalize_writes(created, "finalize created this\n")

    kept = finalize_commit._restore_mission_write_scope(before, mission_dir, written=ledger.written)

    assert not created.exists()
    assert kept == []
    assert recorder.writes_outside_hold == []


def test_restore_keeps_a_created_file_another_writer_edited(scope: tuple[Path, Path]) -> None:
    mission_dir, _tasks_md = scope
    before = finalize_commit._snapshot_mission_write_scope(mission_dir)
    created = mission_dir / "created.md"
    with _finalize_run() as ledger:
        _finalize_writes(created, "finalize created this\n")
    created.write_text("another writer appended\n", encoding="utf-8")

    kept = finalize_commit._restore_mission_write_scope(before, mission_dir, written=ledger.written)

    assert created.read_text(encoding="utf-8") == "another writer appended\n"
    assert kept == [created]


def test_restore_keeps_a_removed_file_another_writer_put_back(scope: tuple[Path, Path]) -> None:
    mission_dir, tasks_md = scope
    before = finalize_commit._snapshot_mission_write_scope(mission_dir)
    tasks_md.unlink()  # finalize removed a tracked file; another writer put a different one back
    tasks_md.write_text("another writer's file\n", encoding="utf-8")

    kept = finalize_commit._restore_mission_write_scope(before, mission_dir, written={})

    assert tasks_md.read_text(encoding="utf-8") == "another writer's file\n"
    assert kept == [tasks_md]


def test_restore_keeps_a_file_another_writer_deleted_and_reports_it(scope: tuple[Path, Path]) -> None:
    """A deletion is a concurrent change too: with a ledger, a file finalize never wrote is not resurrected."""
    mission_dir, tasks_md = scope
    before = finalize_commit._snapshot_mission_write_scope(mission_dir)
    tasks_md.unlink()  # another writer removed it; finalize wrote nothing

    kept = finalize_commit._restore_mission_write_scope(before, mission_dir, written={})

    assert not tasks_md.exists()
    assert kept == [tasks_md]


def test_restore_without_a_ledger_puts_back_a_file_that_is_gone(scope: tuple[Path, Path]) -> None:
    mission_dir, tasks_md = scope
    before = finalize_commit._snapshot_mission_write_scope(mission_dir)
    tasks_md.unlink()

    assert finalize_commit._restore_mission_write_scope(before, mission_dir) == []
    assert tasks_md.read_text(encoding="utf-8") == "original\n"


def test_restore_without_a_ledger_undoes_every_changed_file(scope: tuple[Path, Path]) -> None:
    """A status directory restored by the status guard passes no ledger and keeps the previous restore."""
    mission_dir, tasks_md = scope
    before = finalize_commit._snapshot_mission_write_scope(mission_dir)
    tasks_md.write_text("finalize wrote this\n", encoding="utf-8")

    assert finalize_commit._restore_mission_write_scope(before, mission_dir) == []
    assert tasks_md.read_text(encoding="utf-8") == "original\n"


def _wp02(primary: Path) -> Path:
    wp02 = primary / "tasks" / "WP02-other.md"
    wp02.write_text('---\nwork_package_id: "WP02"\ntitle: "Other"\ndependencies: []\n---\n\n# WP02\n', encoding="utf-8")
    return wp02


def test_a_failed_finalize_keeps_notes_written_during_the_run_and_reports_them(mission: tuple[Path, Path, Path]) -> None:
    """FR-003 (A8): finalize flushes WP01, a foreign writer adds a note to WP02 (never touched) and to WP01, finalize fails.

    Nothing of the foreign writer's is put back; WP01's own frontmatter write is undone only if untouched.
    """
    repo, primary, wp01 = mission
    wp02 = _wp02(primary)
    before = finalize_commit._snapshot_mission_write_scope(primary)
    original_wp01 = wp01.read_bytes()
    guard = StatusSurfaceGuard()

    with _finalize_run() as ledger:
        bootstrap._flush_frontmatter_writes(_bootstrap_state(repo, wp01), validate_only=False, repo_root=repo)
        wp02.write_text(wp02.read_text(encoding="utf-8") + "\nreviewer note on WP02\n", encoding="utf-8")  # a file finalize never wrote
        _, kept = finalize_commit._undo_finalize_write_scope(guard, before, primary, owned_derived_snapshot={}, owned_derived_dir=None, ledger=ledger)

    assert "reviewer note on WP02" in wp02.read_text(encoding="utf-8")
    assert kept == [wp02]
    assert wp01.read_bytes() == original_wp01  # finalize's own, untouched write is undone


def test_a_failed_finalize_keeps_a_note_added_to_a_file_it_wrote(mission: tuple[Path, Path, Path]) -> None:
    repo, primary, wp01 = mission
    before = finalize_commit._snapshot_mission_write_scope(primary)
    guard = StatusSurfaceGuard()

    with _finalize_run() as ledger:
        bootstrap._flush_frontmatter_writes(_bootstrap_state(repo, wp01), validate_only=False, repo_root=repo)
        wp01.write_text(wp01.read_text(encoding="utf-8") + "\nnote added after the flush\n", encoding="utf-8")
        _, kept = finalize_commit._undo_finalize_write_scope(guard, before, primary, owned_derived_snapshot={}, owned_derived_dir=None, ledger=ledger)

    assert "note added after the flush" in wp01.read_text(encoding="utf-8")
    assert kept == [wp01]


def test_the_ledger_records_the_meta_text_inside_the_writing_hold(mission: tuple[Path, Path, Path]) -> None:
    from specify_cli.mission_metadata import locked_update_meta

    repo, primary, _wp = mission
    with _finalize_run() as ledger:
        locked_update_meta(primary, lambda meta: meta.update(target_branch="develop"), repo_root=repo, validate=False)
    text = ledger.text_for(primary / "meta.json")
    assert text is not None
    assert json.loads(text)["target_branch"] == "develop"
    assert text == (primary / "meta.json").read_text(encoding="utf-8")


def test_a_status_append_is_recorded_in_the_ledger_with_the_bytes_of_the_appending_hold(mission: tuple[Path, Path, Path]) -> None:
    from specify_cli.status import StatusEvent
    from specify_cli.status.store import append_event

    _repo, primary, _wp = mission
    event = StatusEvent.from_dict(
        {
            "actor": "t",
            "at": "2026-01-01T00:00:00+00:00",
            "event_id": "01JTEST00000000000000000009",
            "evidence": None,
            "execution_mode": "direct_repo",
            "mission_slug": SLUG,
            "force": False,
            "from_lane": "planned",
            "reason": None,
            "review_ref": None,
            "to_lane": "claimed",
            "wp_id": "WP01",
        }
    )
    append_event(primary, event)  # outside a run: nothing is recorded and nothing raises
    with _finalize_run() as ledger:
        append_event(primary, event)
    assert ledger.written == {(primary / "status.events.jsonl").resolve(): (primary / "status.events.jsonl").read_bytes()}


def test_the_flush_fallback_for_a_vanished_work_package_is_atomic_and_recorded(mission: tuple[Path, Path, Path]) -> None:
    repo, primary, wp01 = mission
    state = _bootstrap_state(repo, wp01)
    wp01.unlink()

    with _finalize_run() as ledger:
        bootstrap._flush_frontmatter_writes(state, validate_only=False, repo_root=repo)

    assert wp01.exists()
    assert ledger.written == {wp01.resolve(): wp01.read_bytes()}


def test_meta_revert_is_a_compare_and_swap_on_what_finalize_wrote(mission: tuple[Path, Path, Path]) -> None:
    _repo, primary, _wp = mission
    meta_path = primary / "meta.json"
    original = meta_path.read_text(encoding="utf-8")
    written = json.dumps({**json.loads(original), "target_branch": "develop"}, indent=2) + "\n"
    meta_path.write_text(written, encoding="utf-8")
    progress = finalize_commit._MetaBranchOverrideProgress()

    meta_path.write_text(written.replace("develop", "release"), encoding="utf-8")  # another writer's change
    message = finalize_commit._revert_unpersisted_target_branch_override(
        meta_path, original, meta_json_persisted=True, meta_commit_progress=progress, written_text=written
    )

    assert message is not None
    assert "another writer" in message
    assert '"release"' in meta_path.read_text(encoding="utf-8")


def test_meta_revert_restores_the_original_when_untouched(mission: tuple[Path, Path, Path]) -> None:
    _repo, primary, _wp = mission
    meta_path = primary / "meta.json"
    original = meta_path.read_text(encoding="utf-8")
    written = json.dumps({**json.loads(original), "target_branch": "develop"}, indent=2) + "\n"
    meta_path.write_text(written, encoding="utf-8")

    message = finalize_commit._revert_unpersisted_target_branch_override(
        meta_path, original, meta_json_persisted=True, meta_commit_progress=finalize_commit._MetaBranchOverrideProgress(), written_text=written
    )

    assert message is None
    assert meta_path.read_text(encoding="utf-8") == original


# ---------------------------------------------------------------------------
# T019 / A10: the remaining frontmatter and tasks.md writers read and write in one hold
# ---------------------------------------------------------------------------

PROBE_WAIT = 0.2
JOIN_SECONDS = 20.0


def _another_thread_is_locked_out(feature_dir: Path, repo: Path) -> bool:
    """Whether a second thread cannot take the Mission write lock right now (it times out)."""
    from specify_cli.status import FeatureStatusLockTimeoutError, mission_write_lock

    outcome: list[bool] = []

    def attempt() -> None:
        try:
            with mission_write_lock(feature_dir, repo_root=repo, timeout=PROBE_WAIT):
                outcome.append(False)
        except FeatureStatusLockTimeoutError:
            outcome.append(True)

    thread = threading.Thread(target=attempt)
    thread.start()
    thread.join(JOIN_SECONDS)
    return outcome == [True]


def _probe_before(monkeypatch: pytest.MonkeyPatch, module: Any, name: str, primary: Path, repo: Path) -> list[bool]:
    """Wrap ``module.name`` so every call first records whether the Mission lock is held by this (calling) thread."""
    real = getattr(module, name)
    seen: list[bool] = []

    def probing(*args: Any, **kwargs: Any) -> Any:
        seen.append(_another_thread_is_locked_out(primary, repo))
        return real(*args, **kwargs)

    monkeypatch.setattr(module, name, probing)
    return seen


def _legacy_wp(primary: Path, name: str = "WP02-legacy.md") -> Path:
    wp_file = primary / "tasks" / name
    wp_file.write_text(
        '---\nwork_package_id: "WP02"\ntitle: "Legacy"\nlane: planned\nagent: claude\nshell_pid: "123"\ndependencies: []\n---\n\n# WP02\n',
        encoding="utf-8",
    )
    return wp_file


def test_strip_mutable_fields_reads_and_writes_in_one_hold(monkeypatch: pytest.MonkeyPatch, mission: tuple[Path, Path, Path]) -> None:
    from specify_cli.migration import strip_frontmatter

    repo, primary, _wp = mission
    legacy = _legacy_wp(primary)
    seen = _probe_before(monkeypatch, strip_frontmatter, "_remove_mutable_fields", primary, repo)

    result = strip_frontmatter.strip_mutable_fields(primary)

    assert seen == [True, True]  # both work packages stripped inside the hold
    assert result.lane_records == {"WP02": "planned"}
    stripped, body = read_frontmatter(legacy)
    assert "lane" not in stripped
    assert stripped["title"] == "Legacy"
    assert body == "\n# WP02\n"


def test_strip_mutable_fields_keeps_a_field_a_concurrent_writer_added(monkeypatch: pytest.MonkeyPatch, mission: tuple[Path, Path, Path]) -> None:
    from specify_cli.frontmatter import locked_update_frontmatter
    from specify_cli.migration import strip_frontmatter

    repo, primary, _wp = mission
    legacy = _legacy_wp(primary)
    errors = _overlap(
        monkeypatch,
        lambda: strip_frontmatter.strip_mutable_fields(primary),
        lambda: locked_update_frontmatter(legacy, lambda fm: fm.update(requirement_refs=["FR-001"]), feature_dir=primary, repo_root=repo),
    )
    assert errors == []
    after, _ = read_frontmatter(legacy)
    assert after["requirement_refs"] == ["FR-001"]
    assert "lane" not in after


def test_backfill_ownership_applies_to_the_frontmatter_it_reads_under_the_lock(monkeypatch: pytest.MonkeyPatch, mission: tuple[Path, Path, Path]) -> None:
    backfill_ownership = importlib.import_module("specify_cli.migration.backfill_ownership")  # the package re-exports the function under this name

    _repo, primary, _wp = mission
    legacy = _legacy_wp(primary)
    real_infer = backfill_ownership.infer_execution_mode

    def infer_then_a_concurrent_writer_lands(*args: Any, **kwargs: Any) -> Any:
        frontmatter, body = read_frontmatter(legacy)  # lands after backfill read the file, before it writes
        frontmatter["requirement_refs"] = ["FR-002"]
        frontmatter["execution_mode"] = "planning_artifact"
        write_frontmatter(legacy, frontmatter, body)
        return real_infer(*args, **kwargs)

    monkeypatch.setattr(backfill_ownership, "infer_execution_mode", infer_then_a_concurrent_writer_lands)
    backfill_ownership.backfill_ownership(primary, SLUG)

    after, _ = read_frontmatter(legacy)
    assert after["requirement_refs"] == ["FR-002"]
    assert after["execution_mode"] == "planning_artifact"  # a field present now is never overwritten
    assert "owned_files" in after  # an absent one is still backfilled


def test_repair_lane_mismatch_reads_and_writes_in_one_hold(monkeypatch: pytest.MonkeyPatch, mission: tuple[Path, Path, Path]) -> None:
    from specify_cli import task_metadata_validation

    repo, primary, _wp = mission
    doing = primary / "tasks" / "doing"
    doing.mkdir()
    legacy = doing / "WP03-legacy.md"
    legacy.write_text('---\nwork_package_id: "WP03"\nlane: planned\n---\n\n# WP03\n', encoding="utf-8")
    seen = _probe_before(monkeypatch, task_metadata_validation, "parse_frontmatter", primary, repo)
    monkeypatch.setattr(task_metadata_validation, "detect_lane_mismatch", lambda _path: (True, "doing", "planned"))

    repaired, error = task_metadata_validation.repair_lane_mismatch(legacy, add_history=False)

    assert (repaired, error) == (True, None)
    assert seen == [True]
    assert "lane: doing" in legacy.read_text(encoding="utf-8")


def test_sweep_rebuilds_meta_normalizes_and_rewrites_in_one_hold(monkeypatch: pytest.MonkeyPatch, mission: tuple[Path, Path, Path]) -> None:
    from specify_cli.upgrade.migrations import m_2_0_6_consistency_sweep as sweep

    repo, primary, _wp = mission
    _legacy_wp(primary)
    (primary / "tasks.md").write_text("**Prompt**: `tasks/planned/WP01-test.md`\n", encoding="utf-8")
    meta_seen = _probe_before(monkeypatch, sweep, "build_baseline_feature_meta", primary, repo)
    render_seen = _probe_before(monkeypatch, sweep, "_render_frontmatter", primary, repo)

    changes, _warnings = sweep._repair_feature(primary, repo, dry_run=False)

    assert meta_seen == [True]  # the meta.json read, rebuild and write are one hold
    assert render_seen and all(render_seen)  # each work package is normalized inside its own hold
    assert (primary / "tasks.md").read_text(encoding="utf-8") == "**Prompt**: `tasks/WP01-test.md`\n"
    assert any("legacy prompt" in change for change in changes)


def test_sweep_dry_run_changes_nothing(mission: tuple[Path, Path, Path]) -> None:
    from specify_cli.upgrade.migrations import m_2_0_6_consistency_sweep as sweep

    repo, primary, wp_file = mission
    legacy = _legacy_wp(primary)
    tasks_md = primary / "tasks.md"
    tasks_md.write_text("**Prompt**: `tasks/planned/WP01-test.md`\n", encoding="utf-8")
    before = (wp_file.read_bytes(), legacy.read_bytes(), tasks_md.read_bytes(), (primary / "meta.json").read_bytes())

    sweep._repair_feature(primary, repo, dry_run=True)

    assert (wp_file.read_bytes(), legacy.read_bytes(), tasks_md.read_bytes(), (primary / "meta.json").read_bytes()) == before


def test_finalize_tasks_md_regeneration_writes_inside_the_hold(monkeypatch: pytest.MonkeyPatch, mission: tuple[Path, Path, Path]) -> None:
    from specify_cli.core.wps_manifest import WorkPackageEntry, WpsManifest

    mission_write = importlib.import_module("specify_cli.status.mission_write")

    repo, primary, _wp = mission
    held_at_write: list[bool] = []
    real_atomic = mission_write.atomic_write

    def spy(path: Path, *args: Any, **kwargs: Any) -> None:
        if path.name == "tasks.md":
            held_at_write.append(holds_status_lock(feature_status_lock_path(repo, COORD_NAME)))
        real_atomic(path, *args, **kwargs)

    monkeypatch.setattr(mission_write, "atomic_write", spy)
    manifest = WpsManifest(work_packages=[WorkPackageEntry(id="WP01", title="T1", requirement_refs=["FR-001"])])

    stale = bootstrap._regenerate_or_report_tasks_md(primary, manifest, SLUG, validate_only=False, json_output=True)

    assert stale is False
    assert held_at_write == [True]
    assert (primary / "tasks.md").exists()


def test_backfill_ownership_heals_a_mission_whose_coordination_key_is_unresolvable(tmp_path: Path) -> None:
    """Like the other healing migrations, the ownership backfill falls back to the directory name (no ``MissionLockKeyUnresolved``)."""
    backfill_ownership = importlib.import_module("specify_cli.migration.backfill_ownership")
    repo = tmp_path / "legacy"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True, capture_output=True)
    feature_dir = repo / "kitty-specs" / "legacy-mission"
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps({"slug": "legacy-mission", "coordination_branch": "kitty/x"}), encoding="utf-8")
    wp_file = feature_dir / "tasks" / "WP01-legacy.md"
    wp_file.write_text('---\nwork_package_id: "WP01"\ntitle: "Legacy"\ndependencies: []\n---\n\n# WP01\n', encoding="utf-8")

    backfill_ownership.backfill_ownership(feature_dir, "legacy-mission")

    healed, body = read_frontmatter(wp_file)
    assert "execution_mode" in healed
    assert body == "\n# WP01\n"
