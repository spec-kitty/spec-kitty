"""Regression tests for ULID mission_id minting at creation time (T019 / FR-201..FR-206).

Concurrency regression tests (WP01, mission
concurrent-template-config-race-4589-01M35M6B, OBL-1/OBL-2/OBL-3) are
appended at the end of this module -- see
``kitty-specs/concurrent-template-config-race-4589-01M35M6B/plan.md``
Section 8 for the full obligation table and revert matrix these pin, and
``kitty-specs/concurrent-template-config-race-4589-01M35M6B/tasks/WP01-concurrent-yaml-cache-race-fix.md``
for the binding WP-level construction notes.
"""

from __future__ import annotations

from contextlib import contextmanager
import json
import subprocess
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from ruamel.yaml.main import YAML as _RuamelYAML
from ulid import ULID

from charter.activation.mission_type_profiles import resolve_mission_type_context
from charter.offering.missions import mission_step_repository as _msr
from charter.offering.missions import mission_type_repository as _mtr
from charter.offering.missions.mission_step_repository import MissionStepRepository
from charter.offering.missions.mission_type_repository import MissionTypeRepository
from charter.offering.missions.repository import MissionTemplateRepository
from specify_cli.core.mission_creation import create_mission_core
from tests._factories import provision_test_charter

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_CORE_MODULE = "specify_cli.core.mission_creation"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_git_repo(repo: Path) -> None:
    """Initialise a minimal git repo with .kittify and kitty-specs."""
    (repo / ".kittify").mkdir(exist_ok=True)
    (repo / "kitty-specs").mkdir(exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init", "--allow-empty"], cwd=repo, capture_output=True, check=True)
    # WP04 fail-closed follow-up: create_mission_core() hard-requires an
    # activated mission type; a bare git-init fixture never ran
    # `spec-kitty init`, so provision the same default charter surface here.
    provision_test_charter(repo)


def _mission_summary(slug: str) -> dict[str, str]:
    title = slug.replace("-", " ").strip() or "test mission"
    return {
        "friendly_name": title.title(),
        "purpose_tldr": f"Deliver {title} cleanly for the team.",
        "purpose_context": (
            f"This mission delivers {title} so product and engineering can move "
            "forward with a clear outcome and shared understanding."
        ),
    }


@contextmanager
def _patched_mission_creation_context(tmp_path: Path):
    """Patch side-effecting mission creation dependencies for identity tests."""
    with (
        patch(f"{_CORE_MODULE}.locate_project_root", return_value=tmp_path),
        patch(f"{_CORE_MODULE}.is_worktree_context", return_value=False),
        patch(f"{_CORE_MODULE}.is_git_repo", return_value=True),
        patch(f"{_CORE_MODULE}.get_current_branch", return_value="main"),
        patch(f"{_CORE_MODULE}._commit_feature_file"),
    ):
        yield


def _run_create(tmp_path: Path, slug: str) -> object:
    """Helper: call create_mission_core with standard mocks."""
    with _patched_mission_creation_context(tmp_path):
        return create_mission_core(tmp_path, slug, **_mission_summary(slug))


# ---------------------------------------------------------------------------
# T3.1 — mission_id minted at creation, ULID-shaped
# ---------------------------------------------------------------------------


def test_mission_id_minted_at_creation(tmp_path: Path) -> None:
    """create_mission_core writes a 26-char ULID mission_id to meta.json."""
    _init_git_repo(tmp_path)
    _run_create(tmp_path, "test-identity")

    mission_dir = next((tmp_path / "kitty-specs").iterdir())
    meta_path = mission_dir / "meta.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text())

    assert "mission_id" in meta
    assert isinstance(meta["mission_id"], str)
    assert len(meta["mission_id"]) == 26, (
        f"Expected 26-char ULID, got {meta['mission_id']!r}"
    )
    # Parses without exception — proves it is a valid ULID
    ULID.from_str(meta["mission_id"])


def test_mission_id_present_in_result_meta(tmp_path: Path) -> None:
    """MissionCreationResult.meta contains mission_id."""
    _init_git_repo(tmp_path)
    result = _run_create(tmp_path, "test-meta-identity")

    assert "mission_id" in result.meta
    assert len(result.meta["mission_id"]) == 26
    ULID.from_str(result.meta["mission_id"])


# ---------------------------------------------------------------------------
# T3.2 — mission_id is NOT derived from prefix scan
# ---------------------------------------------------------------------------


def test_mission_id_is_not_derived_from_prefix_scan(tmp_path: Path) -> None:
    """Two missions with different numeric prefixes get different, independent ULIDs."""
    _init_git_repo(tmp_path)
    result_a = _run_create(tmp_path, "feature-alpha")
    result_b = _run_create(tmp_path, "feature-beta")

    id_a = result_a.meta["mission_id"]
    id_b = result_b.meta["mission_id"]

    assert id_a != id_b, "Two distinct missions must have different mission_ids"
    # Both must parse as valid ULIDs
    ULID.from_str(id_a)
    ULID.from_str(id_b)


# ---------------------------------------------------------------------------
# T3.3 — Concurrent creates do not collide
# ---------------------------------------------------------------------------


def test_concurrent_creates_no_collision(tmp_path: Path) -> None:
    """Spawning two threads each creating a different slug yields two distinct mission_ids."""
    _init_git_repo(tmp_path)
    results: list[dict] = []
    errors: list[Exception] = []

    def create_and_capture(slug: str) -> None:
        try:
            result = create_mission_core(tmp_path, slug, **_mission_summary(slug))
            results.append(result.meta)
        except Exception as exc:
            errors.append(exc)

    with _patched_mission_creation_context(tmp_path):
        t1 = threading.Thread(target=create_and_capture, args=("concurrent-alpha",))
        t2 = threading.Thread(target=create_and_capture, args=("concurrent-beta",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

    assert not errors, f"Thread errors: {errors}"
    assert len(results) == 2
    id_0 = results[0]["mission_id"]
    id_1 = results[1]["mission_id"]
    assert id_0 != id_1, f"Collision detected: both missions got mission_id={id_0!r}"
    # Both must be valid ULIDs
    ULID.from_str(id_0)
    ULID.from_str(id_1)


# ---------------------------------------------------------------------------
# WP01 (mission concurrent-template-config-race-4589-01M35M6B) -- OBL-1/2/3
#
# Two module-level ruamel.yaml.YAML(typ="safe") singletons -- _YAML
# (mission_step_repository.py, "PRIMARY_SITE") and _LAYERED_YAML
# (mission_type_repository.py, "SECOND_SITE") -- are shared across every
# thread and call for the process's lifetime, feeding functools.cache-wrapped
# functions whose cache-miss path is not serialized. See plan.md Sections
# 6/8 for the full fix design and test-obligation table; this section pins
# OBL-1 (forced-interleave content correctness, distinct keys -- the 6a
# proof), OBL-2 (redundant-population count, same key -- the 6b proof), and
# OBL-3 (amended-SC-006 raise-never-degrade regression guard, ALREADY GREEN
# AT BASE -- not red-first, committed alongside the red obligations for
# review-diff cohesion only, per CL-008/plan.md Section 8b). OBL-5
# (cache_clear() mid-population, no deadlock) is added in the production-fix
# commit (T004) once 6b's lock exists to interact with.
# ---------------------------------------------------------------------------


def _cold_cache() -> None:
    """Clear every cache OBL-1/2/3/5 race (plan.md Section 5/9's shared seam).

    Two same-named-looking but deliberately INDEPENDENT cache-clear seams
    (plan.md Section 5): ``MissionTypeRepository.default.cache_clear()``
    clears only ``default()``'s own, separate, ``cls``-keyed built-in cache;
    ``MissionTypeRepository.cache_clear()`` (no ``.default``) clears
    SECOND_SITE's layered-lookup cache. Both must be cold, plus
    ``MissionStepRepository.cache_clear()`` for PRIMARY_SITE.
    """
    MissionStepRepository.cache_clear()
    MissionTypeRepository.default.cache_clear()
    MissionTypeRepository.cache_clear()  # NOT .default -- Section 5's second, independent seam


def _builtin_steps_root() -> Path:
    return MissionTemplateRepository.default_missions_root() / "mission-steps"


def _builtin_mission_types_dirs() -> tuple[Path, ...]:
    return (MissionTemplateRepository.default_missions_root() / "mission_types",)


class _CallCounter:
    """Thread-safe invocation counter (OBL-2's population-count assertions)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.count = 0

    def hit(self) -> None:
        with self._lock:
            self.count += 1


class _PauseHarness:
    """Pause ONE thread strictly inside the shared YAML instance's load window.

    Per plan.md Section 8d (binding constraints on any harness):

    1. The pin is by FILE IDENTITY inside the shared load window -- never
       call order or iteration order (PRIMARY_SITE's walk iterates an
       unsorted ``set``, so iteration order is not a valid pin there).
    2. The timing seam exists, UNEDITED, at both the red commit and the
       green commit. ``_YAML.load``/``_LAYERED_YAML.load`` (module-level
       instance attrs) don't exist post-6a, so this hooks a CLASS-level
       method on ``ruamel.yaml.main.YAML`` itself instead -- both the
       pre-fix shared singleton and the post-fix thread-local instance are
       instances of the same class, so the hook survives 6a's rewrite
       unedited. Combined with a thread-local "path currently being loaded"
       pin, set by wrapping ``_load_step_yaml``/``_load_layered_mission_type_file``
       -- both keep their name and ``Path`` argument across 6a/6b.
    3. The pause lands after ``self.reader.stream`` is assigned (done by the
       real ``get_constructor_parser`` call below), before composition
       completes (``constructor.get_single_data()``, called by the
       original ``.load()`` AFTER ``get_constructor_parser`` returns) --
       empirically confirmed during this WP's T001 spike (see
       ``traces/tooling-friction.md``).
    4. Teardown is function-scoped: installed via the ``monkeypatch``
       fixture, auto-reverted at test end -- never a bare module-level
       patch left in place.
    """

    def __init__(self, monkeypatch: pytest.MonkeyPatch, pause_path: Path) -> None:
        self._monkeypatch = monkeypatch
        self._pause_path = pause_path.resolve()
        self._current_path: threading.local = threading.local()
        self.entered = threading.Event()
        self.release = threading.Event()
        self._paused_once = threading.Event()

        original_get_constructor_parser = _RuamelYAML.get_constructor_parser

        def _patched(yaml_self: Any, stream: Any) -> Any:
            result = original_get_constructor_parser(yaml_self, stream)
            current = getattr(self._current_path, "value", None)
            if current == self._pause_path and not self._paused_once.is_set():
                self._paused_once.set()
                self.entered.set()
                self.release.wait(timeout=15)
            return result

        monkeypatch.setattr(_RuamelYAML, "get_constructor_parser", _patched)

    def pin_step_loader(self) -> None:
        """PRIMARY_SITE: wrap ``_load_step_yaml`` (name/``Path`` arg unchanged by 6a/6b)."""
        original = _msr._load_step_yaml

        def _wrapped(step_file: Path) -> Any:
            self._current_path.value = step_file.resolve()
            try:
                return original(step_file)
            finally:
                self._current_path.value = None

        self._monkeypatch.setattr(_msr, "_load_step_yaml", _wrapped)

    def pin_mission_type_loader(self) -> None:
        """SECOND_SITE: wrap ``_load_layered_mission_type_file`` (name/``Path`` arg unchanged)."""
        original = _mtr._load_layered_mission_type_file

        def _wrapped(yaml_file: Path, *, pack_context: Any = None) -> Any:
            self._current_path.value = yaml_file.resolve()
            try:
                return original(yaml_file, pack_context=pack_context)
            finally:
                self._current_path.value = None

        self._monkeypatch.setattr(_mtr, "_load_layered_mission_type_file", _wrapped)


# ---------------------------------------------------------------------------
# OBL-1 -- forced-interleave content-correctness, DISTINCT cache keys
# (the 6a proof). Fix half isolated: 6a. Revert-cell behavior (plan.md
# Section 8c): Base red both sites; 6a+6b green both sites; 6a
# reverted/6b kept red both sites; 6b reverted/6a kept green both sites.
#
# Both cases use TWO DISTINCT PROJECTS (never one project with two mission
# types) so SECOND_SITE's own same-pack_context lock (6b) can never gate
# entry to this race. Pairing a long monkeypatch-forced pause with a thread
# that could block on ANY lock the paused thread holds is exactly the
# deadlock/false-red shape ARB-002 forbids (plan.md Section 8d item 3) --
# two distinct projects means BOTH PRIMARY_SITE's and SECOND_SITE's cache
# keys differ between the two threads, so neither site's lock (once 6b
# lands) ever has the paused thread holding it against the racer.
# ---------------------------------------------------------------------------


def test_obl1_primary_site_forced_interleave_distinct_keys(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PRIMARY_SITE: racing DISTINCT ``resolve_all_for_mission_type`` keys
    (distinct ``pack_context`` -- two projects) through ``create_mission_core``
    must never corrupt either thread's own captured result off the shared
    ``_YAML`` instance."""
    project_a = tmp_path_factory.mktemp("obl1_primary_a")
    project_b = tmp_path_factory.mktemp("obl1_primary_b")
    _init_git_repo(project_a)
    _init_git_repo(project_b)
    _cold_cache()

    step_root = _builtin_steps_root()
    pause_path = step_root / "software-dev" / "charter" / "step.yaml"
    harness = _PauseHarness(monkeypatch, pause_path)
    harness.pin_step_loader()

    captured: dict[int, dict[str, Any]] = {}
    capture_lock = threading.Lock()
    original_resolve = MissionStepRepository.resolve_all_for_mission_type

    def _spy(self: MissionStepRepository, mission_type_id: str, pack_context: Any = None) -> Any:
        result = original_resolve(self, mission_type_id, pack_context)
        if mission_type_id == "software-dev":
            with capture_lock:
                captured.setdefault(threading.get_ident(), result)
        return result

    monkeypatch.setattr(MissionStepRepository, "resolve_all_for_mission_type", _spy)

    errors: dict[str, BaseException] = {}

    def paused_thread() -> None:
        try:
            with _patched_mission_creation_context(project_a):
                create_mission_core(project_a, "obl1-primary-paused", **_mission_summary("obl1-primary-paused"))
        except BaseException as exc:  # noqa: BLE001
            errors["paused"] = exc
        finally:
            harness.release.set()  # safety net: never leave the racer hanging

    def racer_thread() -> None:
        assert harness.entered.wait(timeout=15), "paused thread never reached the pin"
        try:
            with _patched_mission_creation_context(project_b):
                create_mission_core(project_b, "obl1-primary-racer", **_mission_summary("obl1-primary-racer"))
        except BaseException as exc:  # noqa: BLE001
            errors["racer"] = exc
        finally:
            harness.release.set()

    t1 = threading.Thread(target=paused_thread)
    t2 = threading.Thread(target=racer_thread)
    t1.start()
    t2.start()
    t1.join(timeout=30)
    assert not t1.is_alive(), "paused thread (t1) deadlocked and never finished within the join timeout"
    t2.join(timeout=30)
    assert not t2.is_alive(), "racer thread (t2) deadlocked and never finished within the join timeout"

    assert not errors, f"unexpected errors: {errors}"
    assert t1.ident in captured, "paused thread's own resolve_all_for_mission_type call was never captured"

    # Known-good reference: single-threaded, cache-cleared, uncontended --
    # captured BEFORE any race, per-thread-captured (never a post-join
    # re-read of the now-memoized cache, which would just return whatever
    # got cached first and could hide corruption in the LOSING thread).
    _cold_cache()
    reference = MissionStepRepository(step_root).resolve_all_for_mission_type("software-dev")
    _cold_cache()

    paused_result = captured[t1.ident]
    assert sorted(paused_result.keys()) == sorted(reference.keys())
    for step_id, expected_step in reference.items():
        assert paused_result[step_id].model_dump() == expected_step.model_dump(), (
            f"paused thread's own captured step {step_id!r} was corrupted by "
            "the concurrent racer thread's YAML parse landing on the SAME "
            "shared _YAML instance mid-composition"
        )


def test_obl1_second_site_forced_interleave_distinct_pack_contexts(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SECOND_SITE: racing DISTINCT ``pack_context``\\ s (two projects) through
    ``resolve_mission_type_context``/``_resolve_action_slot`` directly (CL-004's
    outer-call rule, WP caution: NOT through ``_run_create``, whose
    ``_patched_mission_creation_context`` uses process-global
    ``unittest.mock.patch`` -- unsafe for two distinct project roots racing
    in two threads, ARB-002 point 3) must never corrupt either thread's own
    captured ``action_sequence`` off the shared ``_LAYERED_YAML`` instance."""
    project_a = tmp_path_factory.mktemp("obl1_second_a")
    project_b = tmp_path_factory.mktemp("obl1_second_b")
    provision_test_charter(project_a)
    provision_test_charter(project_b)
    _cold_cache()

    mission_types_dirs = _builtin_mission_types_dirs()
    pause_path = mission_types_dirs[0] / "software-dev.yaml"
    harness = _PauseHarness(monkeypatch, pause_path)
    harness.pin_mission_type_loader()

    captured: dict[int, list[str]] = {}
    capture_lock = threading.Lock()
    errors: dict[str, BaseException] = {}

    def paused_thread() -> None:
        try:
            bundle = resolve_mission_type_context(project_a, mission_type="software-dev")
            with capture_lock:
                captured[threading.get_ident()] = bundle.action_sequence
        except BaseException as exc:  # noqa: BLE001
            errors["paused"] = exc
        finally:
            harness.release.set()

    def racer_thread() -> None:
        assert harness.entered.wait(timeout=15), "paused thread never reached the pin"
        try:
            resolve_mission_type_context(project_b, mission_type="software-dev")
        except BaseException as exc:  # noqa: BLE001
            errors["racer"] = exc
        finally:
            harness.release.set()

    t1 = threading.Thread(target=paused_thread)
    t2 = threading.Thread(target=racer_thread)
    t1.start()
    t2.start()
    t1.join(timeout=30)
    assert not t1.is_alive(), "paused thread (t1) deadlocked and never finished within the join timeout"
    t2.join(timeout=30)
    assert not t2.is_alive(), "racer thread (t2) deadlocked and never finished within the join timeout"

    assert not errors, f"unexpected errors: {errors}"
    assert t1.ident in captured, "paused thread's own action_sequence was never captured"

    _cold_cache()
    reference = resolve_mission_type_context(project_a, mission_type="software-dev").action_sequence
    _cold_cache()

    assert captured[t1.ident] == reference, (
        "paused thread's own captured action_sequence was corrupted by the "
        "concurrent racer thread's YAML parse landing on the SAME shared "
        "_LAYERED_YAML instance mid-composition"
    )


# ---------------------------------------------------------------------------
# OBL-2 -- redundant-population COUNT, SAME cache key (the 6b proof). Fix
# half isolated: 6b. Revert-cell behavior (plan.md Section 8c): Base red
# both sites (trivial "seam absent" reason); 6a+6b green both sites,
# count==1; 6a reverted/6b kept green both sites (6b alone still serializes
# to one population); 6b reverted/6a kept red both sites, count==2.
#
# Same project, both threads racing the SAME mission type -- deliberately a
# SAME-key race at both sites (mirrors OBL-4's own natural shape). No long
# monkeypatch pause is used here (only a threading.Barrier for simultaneous
# entry), so there is no ARB-002 deadlock risk: neither thread is ever made
# to hold a lock across a barrier the other thread needs.
# ---------------------------------------------------------------------------


def test_obl2_primary_site_redundant_population_count(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PRIMARY_SITE: two threads racing the IDENTICAL
    ``resolve_all_for_mission_type("software-dev", ...)`` key must walk the
    per-key population unit (``_resolve_all_for_mission_type_uncached``)
    exactly once, never twice."""
    _init_git_repo(tmp_path)
    _cold_cache()

    counter = _CallCounter()
    original_uncached = MissionStepRepository._resolve_all_for_mission_type_uncached

    def _counted(self: MissionStepRepository, mission_type_id: str, pack_context: Any) -> Any:
        if mission_type_id == "software-dev":
            counter.hit()
        return original_uncached(self, mission_type_id, pack_context)

    monkeypatch.setattr(MissionStepRepository, "_resolve_all_for_mission_type_uncached", _counted)

    # Widen the interleaving window (both threads' file reads are fast
    # enough, and the OS page cache warm enough, that a bare
    # threading.Barrier alone does not reliably keep both threads' walks
    # in flight simultaneously -- observed empirically during T002). This
    # is NOT the long, test-controlled, event-gated pause OBL-1 uses (no
    # lock is ever held across it, and it self-releases after a fixed,
    # short duration -- never blocking on the other thread's action), so
    # it carries none of ARB-002's deadlock risk; it only makes the SAME
    # underlying race (present regardless) land inside the assertion
    # window deterministically.
    original_step_yaml = _msr._load_step_yaml

    def _slow_load_step_yaml(step_file: Path) -> Any:
        time.sleep(0.01)
        return original_step_yaml(step_file)

    monkeypatch.setattr(_msr, "_load_step_yaml", _slow_load_step_yaml)

    barrier = threading.Barrier(2)
    errors: dict[str, BaseException] = {}

    def racer(name: str) -> None:
        try:
            barrier.wait(timeout=15)
            create_mission_core(tmp_path, f"obl2-primary-{name}", **_mission_summary(f"obl2-primary-{name}"))
        except BaseException as exc:  # noqa: BLE001
            errors[name] = exc

    # A SINGLE _patched_mission_creation_context enclosing BOTH threads
    # (never one entered/exited per racing thread, which is what
    # _run_create would do here) -- unittest.mock.patch's enter/exit is not
    # safe for two threads concurrently patching the SAME global targets
    # (each patcher instance snapshots "the current value" as its own
    # restore point; overlapping enter/exit from two threads can leave the
    # wrong value installed after both exit, corrupting whichever test runs
    # next in this process). Mirrors test_concurrent_creates_no_collision's
    # own (pre-existing, OBL-4) proven-safe shape: patch once, spawn/join
    # both threads inside that one active context.
    with _patched_mission_creation_context(tmp_path):
        t1 = threading.Thread(target=racer, args=("a",))
        t2 = threading.Thread(target=racer, args=("b",))
        t1.start()
        t2.start()
        t1.join(timeout=30)
        assert not t1.is_alive(), "racer thread 'a' (t1) deadlocked and never finished within the join timeout"
        t2.join(timeout=30)
        assert not t2.is_alive(), "racer thread 'b' (t2) deadlocked and never finished within the join timeout"

    assert not errors, f"unexpected errors: {errors}"
    assert counter.count == 1, (
        "MissionStepRepository._resolve_all_for_mission_type_uncached('software-dev', ...) "
        f"ran {counter.count} times for one cold-cache episode of the SAME key -- "
        "expected exactly one (OBL-2, the redundant-population defense)."
    )


def test_obl2_second_site_redundant_population_count(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SECOND_SITE: two threads racing the IDENTICAL
    ``resolve_layered_mission_types`` key must walk the per-key population
    unit exactly once, never twice.

    Pre-6b/pre-T004, ``resolve_layered_mission_types`` IS the
    ``functools.cache``-decorated walk itself (no separate
    ``..._uncached`` symbol exists yet); this counts calls to
    ``scan_mission_types_dir(mission_types_dirs[0], ...)`` instead -- the
    built-in-equivalent layer's own scan, which the walk (inline today,
    extracted to ``_resolve_layered_mission_types_uncached`` by T004) always
    calls EXACTLY once per population, before and after that refactor. This
    counting seam is never touched by T004's rename/extraction, so it stays
    valid, unedited, at both the red commit and the green commit.
    """
    _init_git_repo(tmp_path)
    _cold_cache()

    mission_types_dirs = _builtin_mission_types_dirs()
    counter = _CallCounter()
    original_scan = _mtr.scan_mission_types_dir

    def _counted(directory: Path, *, pack_context: Any = None) -> Any:
        if directory == mission_types_dirs[0]:
            counter.hit()
        return original_scan(directory, pack_context=pack_context)

    monkeypatch.setattr(_mtr, "scan_mission_types_dir", _counted)

    # Widen the interleaving window -- see the identical note in
    # test_obl2_primary_site_redundant_population_count above (short,
    # self-releasing, no lock ever held across it: none of ARB-002's
    # deadlock risk).
    original_mission_type_file = _mtr._load_layered_mission_type_file

    def _slow_load_mission_type_file(yaml_file: Path, *, pack_context: Any = None) -> Any:
        time.sleep(0.01)
        return original_mission_type_file(yaml_file, pack_context=pack_context)

    monkeypatch.setattr(_mtr, "_load_layered_mission_type_file", _slow_load_mission_type_file)

    barrier = threading.Barrier(2)
    errors: dict[str, BaseException] = {}

    def racer(name: str) -> None:
        try:
            barrier.wait(timeout=15)
            create_mission_core(tmp_path, f"obl2-second-{name}", **_mission_summary(f"obl2-second-{name}"))
        except BaseException as exc:  # noqa: BLE001
            errors[name] = exc

    # A SINGLE _patched_mission_creation_context enclosing BOTH threads --
    # see the identical note in test_obl2_primary_site_redundant_population_count
    # above (unittest.mock.patch enter/exit is not safe from two concurrent
    # threads on the SAME global targets).
    with _patched_mission_creation_context(tmp_path):
        t1 = threading.Thread(target=racer, args=("a",))
        t2 = threading.Thread(target=racer, args=("b",))
        t1.start()
        t2.start()
        t1.join(timeout=30)
        assert not t1.is_alive(), "racer thread 'a' (t1) deadlocked and never finished within the join timeout"
        t2.join(timeout=30)
        assert not t2.is_alive(), "racer thread 'b' (t2) deadlocked and never finished within the join timeout"

    assert not errors, f"unexpected errors: {errors}"
    assert counter.count == 1, (
        "resolve_layered_mission_types's per-key walk unit scanned the "
        f"built-in-equivalent layer {counter.count} times for one cold-cache "
        "episode of the SAME key -- expected exactly one (OBL-2)."
    )


# ---------------------------------------------------------------------------
# OBL-3 -- amended-SC-006 raise-not-degrade regression guard (CL-008). Fix
# half isolated: NONE -- a construction-invariant property. ALREADY GREEN AT
# BASE, both sites -- this is NOT red-first. functools.cache never stores a
# result for a raising call, and neither 6a nor 6b adds a catch-and-degrade
# branch anywhere on either site's population path (a ``with
# _lock_for(key):`` block does not suppress an exception raised inside it).
# Committed alongside the red OBL-1/OBL-2 obligations for review-diff
# cohesion only (plan.md Section 14), as a falsifiable regression guard
# against a future implementation mistake -- never as evidence of the
# corruption race.
# ---------------------------------------------------------------------------


def test_obl3_primary_site_fault_propagates_never_degrades(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fault injected into PRIMARY_SITE's population path (``_add_step_ids_from_dir``,
    called with no surrounding try/except -- ``_load_step_yaml``'s own blanket
    ``except Exception`` would swallow a fault injected INSIDE it, so the
    injection point is deliberately outside that function) propagates to the
    caller unchanged, leaves nothing cached, and a subsequent call re-attempts
    and succeeds. ALREADY GREEN AT BASE -- see module docstring above."""
    _init_git_repo(tmp_path)
    _cold_cache()

    original = _msr._add_step_ids_from_dir

    def _raise(step_ids: set[str], mission_type_dir: Path) -> None:
        raise RuntimeError("obl3-forced-fault-primary")

    monkeypatch.setattr(_msr, "_add_step_ids_from_dir", _raise)
    with pytest.raises(RuntimeError, match="obl3-forced-fault-primary"):
        _run_create(tmp_path, "obl3-primary-fault")

    assert _msr._resolve_all_for_mission_type_cached.cache_info().currsize == 0, (
        "a raising cache-population call must never leave a partial result cached (CL-008's amended SC-006)"
    )

    monkeypatch.setattr(_msr, "_add_step_ids_from_dir", original)
    _cold_cache()
    _run_create(tmp_path, "obl3-primary-retry")  # must succeed once the fault is gone


def test_obl3_second_site_fault_propagates_never_degrades(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fault injected into SECOND_SITE's population path
    (``_load_layered_mission_type_file``, which already propagates everything
    except ``YAMLError`` -- a direct, real construction) propagates to the
    caller unchanged, leaves nothing cached, and a subsequent call re-attempts
    and succeeds. ALREADY GREEN AT BASE -- see module docstring above."""
    _init_git_repo(tmp_path)
    _cold_cache()

    original = _mtr._load_layered_mission_type_file

    def _raise(yaml_file: Path, *, pack_context: Any = None) -> Any:
        raise RuntimeError("obl3-forced-fault-second")

    monkeypatch.setattr(_mtr, "_load_layered_mission_type_file", _raise)
    with pytest.raises(RuntimeError, match="obl3-forced-fault-second"):
        _run_create(tmp_path, "obl3-second-fault")

    assert _mtr.resolve_layered_mission_types.cache_info().currsize == 0, (
        "a raising cache-population call must never leave a partial result cached (CL-008's amended SC-006)"
    )

    monkeypatch.setattr(_mtr, "_load_layered_mission_type_file", original)
    _cold_cache()
    _run_create(tmp_path, "obl3-second-retry")  # must succeed once the fault is gone


# ---------------------------------------------------------------------------
# OBL-5 -- cache_clear() mid-population, no deadlock (NFR-003, spec.md Edge
# Cases). Fix half isolated: 6b (the per-key lock existing) interacting
# correctly with plan.md Section 5's cache-clear contract. Not applicable
# pre-fix (no lock exists yet to interact with cache_clear()) -- added here,
# in the production-fix commit, per the WP prompt's own deferral note (T002
# step 6 lists OBL-5 in the fact table but defers its concrete
# implementation to T004, since it needs 6b's lock to interact with).
# ---------------------------------------------------------------------------


def test_obl5_primary_site_cache_clear_mid_population_no_deadlock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Calling ``MissionStepRepository.cache_clear()`` while a PRIMARY_SITE
    population is in flight (paused mid-load, holding 6b's per-key lock)
    neither deadlocks nor raises; the in-flight population still completes
    with a correct result once released (plan.md Section 5's edge-case
    walkthrough: ``cache_clear()`` only ever touches the ``functools.cache``
    data dict, never the separate ``_locks`` structure 6b introduces)."""
    _init_git_repo(tmp_path)
    _cold_cache()

    step_root = _builtin_steps_root()
    pause_path = step_root / "software-dev" / "charter" / "step.yaml"
    harness = _PauseHarness(monkeypatch, pause_path)
    harness.pin_step_loader()

    errors: dict[str, BaseException] = {}
    result_holder: dict[str, Any] = {}

    def populate() -> None:
        try:
            with _patched_mission_creation_context(tmp_path):
                result_holder["result"] = create_mission_core(
                    tmp_path, "obl5-primary", **_mission_summary("obl5-primary"),
                )
        except BaseException as exc:  # noqa: BLE001
            errors["populate"] = exc

    populate_thread = threading.Thread(target=populate)
    populate_thread.start()
    assert harness.entered.wait(timeout=15), "population thread never reached the pin"

    clear_errors: dict[str, BaseException] = {}

    def clear() -> None:
        try:
            MissionStepRepository.cache_clear()
        except BaseException as exc:  # noqa: BLE001
            clear_errors["clear"] = exc

    clear_thread = threading.Thread(target=clear)
    clear_thread.start()
    clear_thread.join(timeout=5)
    assert not clear_thread.is_alive(), "cache_clear() deadlocked while a population was in flight"
    assert not clear_errors, f"cache_clear() raised: {clear_errors}"

    harness.release.set()
    populate_thread.join(timeout=30)

    assert not errors, f"unexpected errors: {errors}"
    assert "result" in result_holder, "the in-flight population never completed"


def test_obl5_second_site_cache_clear_mid_population_no_deadlock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Calling ``MissionTypeRepository.cache_clear()`` (NOT ``.default``) while
    a SECOND_SITE population is in flight neither deadlocks nor raises; the
    in-flight population still completes with a correct result once
    released."""
    provision_test_charter(tmp_path)
    _cold_cache()

    mission_types_dirs = _builtin_mission_types_dirs()
    pause_path = mission_types_dirs[0] / "software-dev.yaml"
    harness = _PauseHarness(monkeypatch, pause_path)
    harness.pin_mission_type_loader()

    errors: dict[str, BaseException] = {}
    result_holder: dict[str, Any] = {}

    def populate() -> None:
        try:
            bundle = resolve_mission_type_context(tmp_path, mission_type="software-dev")
            result_holder["action_sequence"] = bundle.action_sequence
        except BaseException as exc:  # noqa: BLE001
            errors["populate"] = exc

    populate_thread = threading.Thread(target=populate)
    populate_thread.start()
    assert harness.entered.wait(timeout=15), "population thread never reached the pin"

    clear_errors: dict[str, BaseException] = {}

    def clear() -> None:
        try:
            MissionTypeRepository.cache_clear()
        except BaseException as exc:  # noqa: BLE001
            clear_errors["clear"] = exc

    clear_thread = threading.Thread(target=clear)
    clear_thread.start()
    clear_thread.join(timeout=5)
    assert not clear_thread.is_alive(), "cache_clear() deadlocked while a population was in flight"
    assert not clear_errors, f"cache_clear() raised: {clear_errors}"

    harness.release.set()
    populate_thread.join(timeout=30)

    assert not errors, f"unexpected errors: {errors}"
    assert "action_sequence" in result_holder, "the in-flight population never completed"
