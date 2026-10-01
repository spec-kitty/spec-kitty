"""Issue-pinned red-first regression tests for the RunIndex port.

Mission: runindex-feature-runs-port. These pin the exact reproduction
sequences from the QA reports through the REAL ``get_or_start_run`` entry
point (ADR 2026-07-17-1: a P0/P1 carries a failing-first reproduction test):

- #5390 (P0): a copied project must advance its OWN run cursor, never the
  original folder's; a moved project must continue its in-flight run instead
  of failing ``RUN_STATE_MISSING`` at the stale absolute path; and the index
  must never persist an absolute ``run_dir``.
- #5389 (P1): concurrent ``next`` starts of distinct missions must each retain
  their run-index registration (no lost update).

The boundary is the real store + real engine (no fake): the persisted
``feature-runs.json`` and the run directories are the subject under test.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import shutil
from pathlib import Path
from typing import Any

import pytest

from runtime.next import runtime_bridge_io as io_seam
from runtime.next.runtime_bridge_io import RunStateMissing

pytestmark = [pytest.mark.regression]

_MISSION_TYPE = "research"


def _index_path(repo_root: Path) -> Path:
    return repo_root / ".kittify" / "runtime" / "feature-runs.json"


def _write_meta(repo_root: Path, slug: str, mission_id: str) -> None:
    feature_dir = repo_root / "kitty-specs" / slug
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, Any] = {
        "mission_slug": slug,
        "mission_type": _MISSION_TYPE,
        "mission_id": mission_id,
        "mission_number": None,
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _init_mission(repo_root: Path, slug: str, mission_id: str) -> None:
    repo_root.mkdir(parents=True, exist_ok=True)
    _write_meta(repo_root, slug, mission_id)


# ---------------------------------------------------------------------------
# #5390 — portability (copy / move) + never-persist-absolute
# ---------------------------------------------------------------------------


def test_next_in_copied_project_uses_the_copys_own_run_dir(tmp_path: Path) -> None:
    """#5390: after a filesystem copy, resolving the run must land on the COPY's
    own run directory, never the original folder's — otherwise a subsequent step
    would advance the original's cursor. RED pre-fix (absolute run_dir → resolves
    to the original)."""
    slug = "relocation"
    mission_id = "01COPYAAAAAAAAAAAAAAAAAAAA"
    original = tmp_path / "repo"
    _init_mission(original, slug, mission_id)

    ref_a = io_seam.get_or_start_run(slug, original, _MISSION_TYPE)
    original_state = (Path(ref_a.run_dir) / "state.json").read_bytes()

    copied = tmp_path / "copied-repo"
    shutil.copytree(original, copied)

    ref_b = io_seam.get_or_start_run(slug, copied, _MISSION_TYPE)

    assert Path(ref_b.run_dir).is_relative_to(copied), f"copy resolved a run_dir outside the invoking repo: {ref_b.run_dir}"
    assert not Path(ref_b.run_dir).is_relative_to(original)
    assert ref_b.run_id == ref_a.run_id, "the copy must continue the same run, not restart it"
    # The original's cursor is untouched by a command run in the copy.
    assert (Path(ref_a.run_dir) / "state.json").read_bytes() == original_state


def test_next_after_move_continues_instead_of_run_state_missing(tmp_path: Path) -> None:
    """#5390: moving a project (original path gone) must continue the in-flight
    run from the moved location. RED pre-fix (stale absolute path → RunStateMissing)."""
    slug = "relocation"
    mission_id = "01MOVEAAAAAAAAAAAAAAAAAAAA"
    original = tmp_path / "repo"
    _init_mission(original, slug, mission_id)

    ref_a = io_seam.get_or_start_run(slug, original, _MISSION_TYPE)
    run_id = ref_a.run_id

    moved = tmp_path / "moved-repo"
    shutil.move(str(original), str(moved))

    try:
        ref_b = io_seam.get_or_start_run(slug, moved, _MISSION_TYPE)
    except RunStateMissing as exc:  # pragma: no cover - this is the pre-fix defect
        pytest.fail(f"moved project wrongly refused with RUN_STATE_MISSING: {exc}")

    assert ref_b.run_id == run_id
    assert Path(ref_b.run_dir).is_relative_to(moved)
    assert (Path(ref_b.run_dir) / "state.json").exists()


def test_run_index_never_persists_an_absolute_run_dir(tmp_path: Path) -> None:
    """#5390 root cause: the persisted ``run_dir`` must be a repo-relative token,
    never an absolute path. RED pre-fix."""
    slug = "relocation"
    mission_id = "01TOKENAAAAAAAAAAAAAAAAAAA"
    repo = tmp_path / "repo"
    _init_mission(repo, slug, mission_id)

    io_seam.get_or_start_run(slug, repo, _MISSION_TYPE)

    index = json.loads(_index_path(repo).read_text(encoding="utf-8"))
    entry = index[mission_id]
    stored = entry["run_dir"]
    assert not Path(stored).is_absolute(), f"index persisted an absolute run_dir: {stored!r}"
    # And it still resolves, inside the invoking repo.
    assert (repo / stored / "state.json").exists()


# ---------------------------------------------------------------------------
# #5389 — concurrent distinct-mission starts must not lose registrations
# ---------------------------------------------------------------------------


def _concurrent_start_worker(barrier: Any, repo_root_str: str, slug: str) -> None:
    # SPEC_KITTY_NO_UPGRADE_CHECK is set by the parent (monkeypatch) and inherited
    # through the fork context, so the worker needs no os.environ mutation of its own.
    import contextlib  # noqa: PLC0415

    from runtime.next import runtime_bridge_io as io  # noqa: PLC0415

    with contextlib.suppress(Exception):  # keep peers from hanging if one errors early
        barrier.wait(timeout=60)
    io.get_or_start_run(slug, Path(repo_root_str), _MISSION_TYPE)


def test_concurrent_distinct_mission_starts_retain_every_registration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#5389 (two-process): concurrent ``next`` starts of distinct missions must
    all survive in the run index. RED pre-fix (unlocked read-modify-write → lost
    update); deterministically GREEN post-fix (the lock serializes the writes)."""
    # Set in the parent so the forked workers inherit it (no per-worker os.environ
    # mutation — keeps the sealed subprocess-entry global-state class at its cap).
    monkeypatch.setenv("SPEC_KITTY_NO_UPGRADE_CHECK", "1")
    repo = tmp_path / "repo"
    count = 2  # "two starts suffice" (#5389); a true two-process concurrent start
    missions = [(f"race-{i}", f"01RACE{i:020d}") for i in range(count)]
    for slug, mission_id in missions:
        _init_mission(repo, slug, mission_id)

    ctx = mp.get_context("fork")
    barrier = ctx.Barrier(count)
    procs = [ctx.Process(target=_concurrent_start_worker, args=(barrier, str(repo), slug)) for slug, _ in missions]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=90)
        assert p.exitcode == 0, "a concurrent start subprocess failed or hung"

    index = json.loads(_index_path(repo).read_text(encoding="utf-8"))
    indexed_ids = set(index.keys())
    expected_ids = {mission_id for _, mission_id in missions}
    assert expected_ids <= indexed_ids, f"concurrent starts lost registrations: missing {expected_ids - indexed_ids}"
    for mission_id in expected_ids:
        stored = index[mission_id]["run_dir"]
        assert (repo / stored).exists() or Path(stored).exists()


def test_forced_interleave_concurrent_start_does_not_lose_registration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#5389 (deterministic): force two starts to both read the index BEFORE
    either writes (a sleep injected after each in-memory load). RED pre-fix
    (second write clobbers the first); GREEN post-fix (the locked section re-reads
    and merges, and the sleep then falls INSIDE the lock so peers never interleave)."""
    import threading
    import time

    repo = tmp_path / "repo"
    missions = [("race-a", "01AAAA000000000000000000AA"), ("race-b", "01BBBB000000000000000000BB")]
    for slug, mission_id in missions:
        _init_mission(repo, slug, mission_id)

    real_load = io_seam._load_run_index

    def _slow_load(repo_root: Path) -> Any:
        result = real_load(repo_root)
        time.sleep(0.4)
        return result

    monkeypatch.setattr(io_seam, "_load_run_index", _slow_load)

    start = threading.Barrier(len(missions))
    errors: list[BaseException] = []

    def _worker(slug: str) -> None:
        try:
            start.wait(timeout=30)
            io_seam.get_or_start_run(slug, repo, _MISSION_TYPE)
        except BaseException as exc:  # noqa: BLE0001 - surface to the assertion below
            errors.append(exc)

    threads = [threading.Thread(target=_worker, args=(slug,)) for slug, _ in missions]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert not errors, f"a concurrent start raised: {errors}"
    index = json.loads(_index_path(repo).read_text(encoding="utf-8"))
    expected_ids = {mission_id for _, mission_id in missions}
    assert expected_ids <= set(index.keys()), f"forced-interleave lost a registration: missing {expected_ids - set(index.keys())}"


def test_same_mission_concurrent_start_yields_one_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#5389 (same-mission): two concurrent starts of the SAME mission must
    converge on ONE run — one index entry, and no orphaned second run directory
    left behind. GREEN post-fix (inside-lock existence recheck + orphan cleanup)."""
    import threading
    import time

    repo = tmp_path / "repo"
    slug, mission_id = "solo", "01SOLO0000000000000000SOLO"
    _init_mission(repo, slug, mission_id)

    real_load = io_seam._load_run_index

    def _slow_load(repo_root: Path) -> Any:
        result = real_load(repo_root)
        time.sleep(0.3)
        return result

    monkeypatch.setattr(io_seam, "_load_run_index", _slow_load)

    start = threading.Barrier(2)
    refs: list[Any] = []
    errors: list[BaseException] = []

    def _worker() -> None:
        try:
            start.wait(timeout=30)
            refs.append(io_seam.get_or_start_run(slug, repo, _MISSION_TYPE))
        except BaseException as exc:  # noqa: BLE0001
            errors.append(exc)

    threads = [threading.Thread(target=_worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert not errors, f"a concurrent same-mission start raised: {errors}"
    index = json.loads(_index_path(repo).read_text(encoding="utf-8"))
    assert set(index.keys()) == {mission_id}
    assert len({r.run_id for r in refs}) == 1, "the two callers disagreed on the run id"
    runs_root = repo / ".kittify" / "runtime" / "runs"
    surviving = [p for p in runs_root.iterdir() if (p / "state.json").exists()]
    assert len(surviving) == 1, f"expected one surviving run dir, found {[p.name for p in surviving]}"
