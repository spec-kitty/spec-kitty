"""Scope: adversarial tests for migration robustness — atomic writes, concurrency, permissions.

Known coverage gap (#4866 pre-merge squad finding pr-merged-004, recorded not
fixed -- severity 2, non-blocking): ``TestVenvCorruptionHazardFR003b`` covers
a dedicated ``UV_PROJECT_ENVIRONMENT`` venv that is present+correct
(matches the current interpreter) and present+wrong-version (a deliberately
mismatched interpreter), but never the case where the target venv is
ABSENT. Empirically, ``uv run --frozen --no-sync`` against a nonexistent
``UV_PROJECT_ENVIRONMENT`` silently creates an empty ad hoc venv (exit 0,
no warning) rather than failing -- untested here. Not covered because (a)
that behavior belongs to ``uv`` itself, not any spec-kitty ``src/`` code,
so a passing test would only pin a third-party tool's current behavior, and
(b) exercising a genuinely-absent target is the one variant most likely to
need network interpreter resolution on an unfamiliar host, which this
mission's own operating constraints forbid triggering. Full rationale in
``kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/tracer-design-decisions.md``
(the "Post-merge pre-merge-squad fix (pr-merged-004)" entry).
"""

from __future__ import annotations

import ast
import multiprocessing
import os
import shutil
import subprocess
import sys
import time
import uuid
from kernel.clock import now_utc
from pathlib import Path
from typing import Any

import pytest
import yaml

from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations.base import BaseMigration, MigrationResult
from specify_cli.upgrade.migrations.m_0_12_1_remove_kitty_specs_from_gitignore import (
    RemoveKittySpecsFromGitignoreMigration,
)
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.runner import MigrationRunner
import contextlib

# Get migrations directory path
MIGRATIONS_DIR = Path(__file__).parents[2] / "src" / "specify_cli" / "upgrade" / "migrations"

# NOTE (#4866 WP-fix pr-merged-001): deliberately NO module-level `pytestmark`
# here. pytest marks are additive down the module -> class -> function chain,
# so a module-level `fast` cannot be "cleared" by a class-level override (see
# TestVenvCorruptionHazardFR003b below, which must NOT carry `fast`). Instead,
# every class in this module declares its own `pytestmark` explicitly. This
# reproduces the exact prior collection behaviour for every class except
# TestVenvCorruptionHazardFR003b, whose network-dependent subprocess venv
# builds must never be collected by the nightly `-m "fast or unit"` selector
# (`.github/workflows/ci-nightly.yml`'s `interpreter-matrix` job).

LOCK_FILENAME = ".upgrade.lock"
FLAKY_MARKER = ".kittify/.flaky-migration"


class LockingMigration(BaseMigration):
    migration_id = "0.0.1_locking_migration"
    description = "Test migration that uses a file lock"
    target_version = "0.0.1"

    def detect(self, project_path: Path) -> bool:
        return True

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        lock_path = project_path / LOCK_FILENAME
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return False, "Upgrade lock already held"
        self._lock_fd = fd
        self._lock_path = lock_path
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        try:
            time.sleep(0.6)
            return MigrationResult(success=True, changes_made=["Lock acquired"])
        finally:
            lock_fd = getattr(self, "_lock_fd", None)
            lock_path = getattr(self, "_lock_path", None)
            if lock_fd is not None:
                os.close(lock_fd)
            if lock_path is not None:
                with contextlib.suppress(OSError):
                    lock_path.unlink()


class FlakyMigration(BaseMigration):
    migration_id = "0.0.2_flaky_migration"
    description = "Fails once, then succeeds"
    target_version = "0.0.2"

    def detect(self, project_path: Path) -> bool:
        return True

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        marker = project_path / FLAKY_MARKER
        if marker.exists():
            return MigrationResult(success=True, changes_made=["Recovered"])

        if not dry_run:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("failed", encoding="utf-8")

        return MigrationResult(success=False, errors=["Simulated migration failure"])


@pytest.fixture()
def registry_restore() -> Any:
    original = MigrationRegistry._migrations.copy()
    yield
    MigrationRegistry._migrations = original


@pytest.fixture()
def migration_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    kittify_dir = project / ".kittify"
    kittify_dir.mkdir(parents=True)
    metadata = ProjectMetadata(
        version="0.0.0",
        initialized_at=now_utc(),
        python_version="3.11",
        platform="test",
        platform_version="test",
    )
    metadata.save(kittify_dir)
    return project


def _register_migrations(*migrations: type[BaseMigration]) -> None:
    MigrationRegistry.clear()
    for migration in migrations:
        MigrationRegistry.register(migration)


def _run_upgrade_concurrent(
    project_path: str,
    ready_queue: multiprocessing.Queue,
    go_event: multiprocessing.Event,
    result_queue: multiprocessing.Queue,
) -> None:
    _register_migrations(LockingMigration)
    ready_queue.put("ready")
    go_event.wait()
    runner = MigrationRunner(Path(project_path))
    result = runner.upgrade("0.0.1", include_worktrees=False, force=True)
    result_queue.put((result.success, result.errors))


class TestAtomicWrites:
    pytestmark = [pytest.mark.adversarial, pytest.mark.fast]

    def test_metadata_save_interruption_preserves_original(self, tmp_path: Path, monkeypatch):
        """Atomic writes preserve the original file when serialization crashes.

        With atomic_write(), the crash occurs during StringIO serialization
        (before os.replace), so the on-disk file remains intact.
        """
        # Arrange
        kittify_dir = tmp_path / ".kittify"
        kittify_dir.mkdir(parents=True)
        metadata = ProjectMetadata(
            version="0.0.0",
            initialized_at=now_utc(),
            python_version="3.11",
            platform="test",
            platform_version="test",
        )
        metadata.save(kittify_dir)
        metadata_path = kittify_dir / "metadata.yaml"
        before = metadata_path.read_text(encoding="utf-8")
        # Assumption check
        assert "spec_kitty:" in before or "Spec Kitty" in before

        import specify_cli.upgrade.metadata as metadata_module

        def _boom(*_args, **_kwargs):
            raise RuntimeError("simulated crash")

        monkeypatch.setattr(metadata_module.yaml, "dump", _boom)
        # Act / Assert
        with pytest.raises(RuntimeError):
            metadata.save(kittify_dir)

        after = metadata_path.read_text(encoding="utf-8")
        # Atomic writes guarantee: crash during serialization preserves original
        assert after == before


@pytest.mark.slow
class TestConcurrentMigration:
    pytestmark = [pytest.mark.adversarial, pytest.mark.fast]

    def test_concurrent_upgrade_handled(self, migration_project: Path, registry_restore: Any):
        """Exactly one of two concurrent upgrade processes succeeds; the other is blocked."""
        # Arrange
        ctx = multiprocessing.get_context("spawn")
        ready_queue: multiprocessing.Queue = ctx.Queue()
        result_queue: multiprocessing.Queue = ctx.Queue()
        go_event = ctx.Event()
        # Assumption check
        assert migration_project.exists()
        # Act
        processes = [
            ctx.Process(
                target=_run_upgrade_concurrent,
                args=(str(migration_project), ready_queue, go_event, result_queue),
            )
            for _ in range(2)
        ]

        for process in processes:
            process.start()

        for _ in range(2):
            ready_queue.get(timeout=10)

        go_event.set()

        results = [result_queue.get(timeout=20) for _ in range(2)]

        for process in processes:
            process.join(timeout=20)
        # Assert
        successes = [success for success, _errors in results]
        assert successes.count(True) == 1
        assert successes.count(False) == 1
        assert any(
            any("Cannot apply" in err or "Upgrade lock" in err for err in errors)
            for success, errors in results
            if not success
        )


def _extract_uv_run_argv_prefix(source_path: Path, function_name: str) -> list[str]:
    """Extract the literal ``uv run`` argv prefix from the first
    ``subprocess.run([...])`` call inside ``function_name`` in ``source_path``,
    up to and including the ``"python"`` element.

    Reads the REAL call site via AST rather than duplicating its argv by
    hand, so this regression test tracks the live source: if either fixed
    call site is ever reverted to its old bare-``uv run`` shape, this
    extraction reverts with it and the hazard assertion below goes red again
    automatically -- the revert-check this mission's red-first discipline
    requires, made structural instead of a one-time manual check.
    """
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    func_node = next(
        (node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == function_name),
        None,
    )
    assert func_node is not None, f"{function_name!r} not found in {source_path}"

    matching = [
        node
        for node in ast.walk(func_node)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "run" and node.args and isinstance(node.args[0], ast.List)
    ]
    assert len(matching) == 1, (
        f"expected exactly one .run([...]) call inside {function_name!r} "
        f"({source_path}), found {len(matching)} -- a second matching call "
        "site would otherwise be silently shadowed by this extractor "
        "(#4866 pr-merged-003)"
    )
    call_node = matching[0]

    prefix: list[str] = []
    for elt in call_node.args[0].elts:
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
            prefix.append(elt.value)
            if elt.value == "python":
                return prefix
        else:
            # First non string-literal element (e.g. `str(driver_script)`
            # or an f-string) -- the fixed argv prefix is always plain
            # string literals up to and including "python", so stop here.
            return prefix
    return prefix


def _new_home_scratch_venv_path() -> Path:
    """A scratch ``UV_PROJECT_ENVIRONMENT`` directory path rooted under this
    checkout (on ``/home``, never pytest's ``tmp_path`` -- which resolves
    under system ``/tmp``, tmpfs/RAM on hosts this mission's instructions
    warn about -- and never the checkout's own ``.venv`` / ``.venv313`` /
    ``.venv312``, which WP01's baseline and WP05's re-measurement depend on).
    The name matches the repo's ``.venv*/`` gitignore glob. Callers must
    remove the directory unconditionally (``finally``) regardless of test
    outcome.
    """
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / f".venv-hazard-test-{uuid.uuid4().hex[:8]}"


class TestExtractUvRunArgvPrefixUniqueness:
    """#4866 pre-merge squad finding pr-merged-003.

    ``_extract_uv_run_argv_prefix`` returned on the FIRST matching
    ``subprocess.run([...])`` call inside the target function, with no
    uniqueness assertion -- unlike its sibling
    ``_find_interpreter_matrix_run_step``
    (``tests/ci/test_interpreter_matrix_env_pinning.py``), which asserts
    ``len(matching) == 1``. Inert today (each guarded call site has exactly
    one matching call), but a future second matching call added earlier in
    the same target function would be silently shadowed rather than failing
    loud. This test plants a synthetic function with TWO matching calls and
    asserts the extractor now fails loudly instead of silently returning the
    first one.
    """

    pytestmark = [pytest.mark.adversarial, pytest.mark.fast]

    _TWO_MATCHING_CALLS_SOURCE = """
import subprocess


def call_uv_twice():
    subprocess.run(["uv", "run", "--frozen", "python", "-c", "print('first')"])
    subprocess.run(["uv", "run", "--frozen", "python", "-c", "print('second')"])
"""

    def test_two_matching_call_sites_fail_loudly_not_silently_shadowed(self, tmp_path: Path) -> None:
        source_path = tmp_path / "two_calls.py"
        source_path.write_text(self._TWO_MATCHING_CALLS_SOURCE, encoding="utf-8")

        with pytest.raises(AssertionError, match="call_uv_twice"):
            _extract_uv_run_argv_prefix(source_path, "call_uv_twice")

    def test_single_matching_call_site_still_extracts_normally(self, tmp_path: Path) -> None:
        """Negative control: the uniqueness assertion must not break the
        single-match case the extractor exists to serve."""
        source_path = tmp_path / "one_call.py"
        source_path.write_text(
            'import subprocess\n\n\ndef call_uv_once():\n    subprocess.run(["uv", "run", "--frozen", "python", "-c", "print(1)"])\n',
            encoding="utf-8",
        )
        assert _extract_uv_run_argv_prefix(source_path, "call_uv_once") == ["uv", "run", "--frozen", "python"]


class TestVenvCorruptionHazardFR003b:
    """FR-003(b) regression checks for the venv-corruption hazard (#4866 WP04).

    ``test_concurrent_upgrade_handled`` above is the test whose
    multiprocessing-spawn traceback first surfaced this hazard by accident: a
    shared project venv silently rebuilt from Python 3.13 down to 3.11
    mid-``pytest -n auto`` run. WP04's investigation (evidence in
    ``kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/tracer-tooling-friction.md``)
    reproduced the mechanism directly, isolated from pytest/xdist entirely:
    any bare ``uv run --frozen`` call that omits ``--python``/``--all-extras``
    consults the repo's ``.python-version`` pin (3.11.15) and unconditionally
    rebuilds whatever ``UV_PROJECT_ENVIRONMENT`` (or the default ``.venv``)
    currently names to match it -- dropping extras -- REGARDLESS of whether
    that path is a dedicated, already-populated 3.13 venv.

    Two live call sites do exactly this today:
    ``tests/charter/test_interview_mapping_mission_alias.py`` (the
    ``subprocess.run(["uv", "run", "--frozen", "python", ...])`` call in
    ``test_synthetic_mission_type_is_picked_up_by_both_rosters``) and
    ``tests/docs/test_docs_index.py`` (the same shape in
    ``test_render_index_is_byte_stable_across_hash_seeds``). Both are
    confirmed culprits -- isolating either file alone under ``-n auto``
    against a fresh, isolated 3.13 scratch venv reproduced the corruption on
    its own. Both are OUTSIDE this WP's ``owned_files``
    (``tests/upgrade/**``, ``tests/specify_cli/upgrade/**``,
    ``tests/specify_cli/skills/**``) -- the WP prompt's own suspicion of the
    upgrade/skill-installer families did not pan out; grep + reproduction
    found nothing there -- so they are not fixed in this WP. See follow-up
    issue #4922 for the exact fix (pin ``--python``/``--all-extras`` on
    those two call sites) and the full reproduction evidence.

    The fix landed by THIS WP -- a per-interpreter ``UV_PROJECT_ENVIRONMENT``
    pin on ``ci-nightly.yml``'s ``interpreter-matrix`` job -- is containment,
    not closure: it stops a corrupted resync from ever reaching a SHARED
    default ``.venv`` path (protecting the primary dev checkout and any
    other concurrent process). WP04's own reproduction proved it does NOT
    prevent that leg's own dedicated venv from still being downgraded by the
    two call sites above -- a bare ``uv run --frozen`` inherits and targets
    whatever ``UV_PROJECT_ENVIRONMENT`` already names, pin or no pin.

    Marker gating (#4866 pr-merged-001, pre-merge squad finding; refined by
    pr-fresh-001): this class carries ONLY ``adversarial`` at class level --
    never ``fast`` -- unlike every other class in this module. Two of these
    tests spawn real ``uv`` subprocesses that build scratch venvs over the
    network with no skip/availability guard; running them under a nominally
    "fast" selector (the nightly ``-m "fast or unit"`` interpreter-matrix
    step this mission repairs) is a flakiness hazard, not a time-budget one
    (measured ~2s/test with interpreters already cached -- the risk is an
    unguarded network fetch turning an ostensibly fast/unit run red). Keeping
    those two tests out of `fast`/`unit` is therefore load-bearing.
    ``test_interpreter_matrix_job_pins_a_dedicated_project_environment``
    below is the exception: it is a pure static YAML-parse assertion with no
    subprocess, no venv build, and no network access, so it carries its own
    ``@pytest.mark.fast`` to keep it selected by both ``make test-fast`` and
    the nightly leg. Verify with ``pytest
    tests/upgrade/test_migration_robustness.py -m "fast or unit" -k
    TestVenvCorruptionHazardFR003b --collect-only`` (expect exactly 1
    collected -- the static test only) vs. running the class directly, or
    under ``make test-full`` (which selects ``-m "not stress and not
    timing"`` and therefore still runs it), which must still collect and run
    all 4 tests.
    """

    pytestmark = [pytest.mark.adversarial]

    @pytest.mark.fast
    def test_interpreter_matrix_job_pins_a_dedicated_project_environment(self) -> None:
        """FR-003(b): the interpreter-matrix job must pin
        `UV_PROJECT_ENVIRONMENT` so a nested unpinned `uv run` call can, at
        worst, corrupt only that leg's own dedicated venv -- never a default
        `.venv` a concurrent process elsewhere might share.
        """
        workflow_path = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci-nightly.yml"
        with workflow_path.open(encoding="utf-8") as handle:
            workflow = yaml.safe_load(handle)
        job = workflow["jobs"]["interpreter-matrix"]

        job_env = job.get("env") or {}
        assert "UV_PROJECT_ENVIRONMENT" in job_env, (
            "the interpreter-matrix job must pin UV_PROJECT_ENVIRONMENT "
            "(#4866 WP04) so a nested `uv run` call inside any test cannot "
            "silently rebuild a SHARED default `.venv` path; job env keys "
            f"found: {sorted(job_env)}"
        )
        pinned_value = job_env["UV_PROJECT_ENVIRONMENT"]
        assert "${{ matrix.python-version }}" in pinned_value, (
            f"the pin must be scoped per interpreter (contain `${{{{ matrix.python-version }}}}`) so distinct legs never share a path; got: {pinned_value!r}"
        )

    @pytest.mark.slow
    def test_a_well_pinned_nested_uv_run_leaves_a_dedicated_venv_untouched(self, tmp_path: Path) -> None:
        """Positive control for the containment half of the fix: a nested
        `uv run --frozen` call that DOES carry `--python`/`--all-extras` (the
        same shape WP03 already pinned on this job's own top-level `uv run`
        step, af011bacd) must not disturb a dedicated
        `UV_PROJECT_ENVIRONMENT`-pinned venv it targets. Runs a REAL
        subprocess against a throwaway scratch venv (never the repo's own
        `.venv`) built with the CURRENTLY RUNNING interpreter, so it needs no
        network fetch of a second interpreter.
        """
        if shutil.which("uv") is None:
            pytest.skip("uv not on PATH")

        repo_root = Path(__file__).resolve().parents[2]
        version = f"{sys.version_info.major}.{sys.version_info.minor}"
        scratch_env = tmp_path / ".venv-scratch"
        env = dict(os.environ)
        env["UV_PROJECT_ENVIRONMENT"] = str(scratch_env)

        sync = subprocess.run(
            ["uv", "sync", "--frozen", "--all-extras", "--python", version],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert sync.returncode == 0, f"scratch sync failed: {sync.stdout}\n{sync.stderr}"

        before = (scratch_env / "pyvenv.cfg").read_text(encoding="utf-8")

        pinned = subprocess.run(
            ["uv", "run", "--frozen", "--all-extras", "--python", version, "python", "-c", "print('ok')"],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert pinned.returncode == 0, f"pinned nested uv run failed: {pinned.stdout}\n{pinned.stderr}"

        after = (scratch_env / "pyvenv.cfg").read_text(encoding="utf-8")
        assert after == before, (
            "a well-pinned nested `uv run --frozen --python ... --all-extras` "
            "must not rebuild the dedicated scratch venv it already targets; "
            f"pyvenv.cfg changed:\nbefore={before!r}\nafter={after!r}"
        )

    @pytest.mark.slow
    @pytest.mark.parametrize(
        ("source_relpath", "function_name"),
        [
            (
                "tests/charter/test_interview_mapping_mission_alias.py",
                "test_synthetic_mission_type_is_picked_up_by_both_rosters",
            ),
            (
                "tests/docs/test_docs_index.py",
                "test_render_index_is_byte_stable_across_hash_seeds",
            ),
        ],
    )
    def test_named_call_site_argv_does_not_rebuild_a_mismatched_dedicated_venv(self, source_relpath: str, function_name: str) -> None:
        """RED-FIRST end-to-end hazard test (#4866 WP04 scope extension --
        follow-up #4922, now authorized in-mission per C-011).

        Extracts the REAL ``uv run`` argv prefix the named call site uses
        (via ``_extract_uv_run_argv_prefix``, AST-driven -- not a
        hand-copied duplicate) and runs it, unmodified, against a scratch
        ``UV_PROJECT_ENVIRONMENT`` venv deliberately built for Python 3.12 --
        a DIFFERENT interpreter than the repo's own ``.python-version`` pin
        (3.11.15) that a bare ``uv run --frozen`` silently resyncs toward.
        Asserts the scratch venv's ``pyvenv.cfg`` is byte-identical
        before/after -- i.e. the nested call did not resync/rebuild it.

        Before this WP's fix: both call sites' argv was a bare
        ``["uv", "run", "--frozen", "python"]`` with no ``--no-sync`` guard,
        so uv silently resynced the 3.12 scratch venv down to 3.11.15,
        dropping every optional extra in the process (reproduced manually
        and recorded in ``tracer-design-decisions.md``) -- this assertion
        was RED. After the fix lands ``--no-sync`` on both argv lists, the
        AST-extracted prefix carries that flag and this assertion is GREEN.
        Revert either fixed call site and this test goes red again for that
        parametrization -- the mechanism this mission's reviewer uses as the
        revert-check.
        """
        if shutil.which("uv") is None:
            pytest.skip("uv not on PATH")

        repo_root = Path(__file__).resolve().parents[2]
        source_path = repo_root / source_relpath
        argv_prefix = _extract_uv_run_argv_prefix(source_path, function_name)
        assert argv_prefix[:2] == ["uv", "run"], f"expected an `uv run` invocation, extracted {argv_prefix!r} from {function_name} in {source_relpath}"

        mismatched_python_version = "3.12"
        scratch_env = _new_home_scratch_venv_path()
        env = dict(os.environ)
        env["UV_PROJECT_ENVIRONMENT"] = str(scratch_env)
        try:
            sync = subprocess.run(
                [
                    "uv",
                    "sync",
                    "--frozen",
                    "--all-extras",
                    "--python",
                    mismatched_python_version,
                ],
                cwd=repo_root,
                env=env,
                capture_output=True,
                text=True,
                timeout=180,
            )
            assert sync.returncode == 0, f"scratch sync failed: {sync.stdout}\n{sync.stderr}"

            before = (scratch_env / "pyvenv.cfg").read_text(encoding="utf-8")

            argv = [*argv_prefix, "-c", "print('hazard-test-ok')"]
            result = subprocess.run(
                argv,
                cwd=repo_root,
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
            )
            assert result.returncode == 0, f"argv={argv!r} failed: stdout={result.stdout!r} stderr={result.stderr!r}"
            assert "hazard-test-ok" in result.stdout

            after = (scratch_env / "pyvenv.cfg").read_text(encoding="utf-8")
            assert after == before, (
                f"{function_name}'s real `uv run` argv ({argv_prefix!r}) rebuilt a "
                f"dedicated scratch venv pinned to Python {mismatched_python_version} "
                "-- the venv-corruption hazard this WP fixes. "
                f"pyvenv.cfg changed:\nbefore={before!r}\nafter={after!r}"
            )
        finally:
            shutil.rmtree(scratch_env, ignore_errors=True)


class TestPartialMigrationRecovery:
    pytestmark = [pytest.mark.adversarial, pytest.mark.fast]

    def test_failed_migration_can_retry(self, migration_project: Path, registry_restore: Any):
        """A flaky migration that fails on first run succeeds on retry."""
        # Arrange
        _register_migrations(FlakyMigration)
        runner = MigrationRunner(migration_project)
        # Assumption check
        assert migration_project.exists()
        # Act
        first = runner.upgrade("0.0.2", include_worktrees=False, force=True)
        second = runner.upgrade("0.0.2", include_worktrees=False, force=True)
        # Assert
        assert not first.success
        assert second.success
        metadata = ProjectMetadata.load(migration_project / ".kittify")
        assert metadata is not None
        assert metadata.has_migration(FlakyMigration.migration_id)


class TestPermissionErrors:
    pytestmark = [pytest.mark.adversarial, pytest.mark.fast]

    def test_readonly_gitignore_clear_error(self, migration_project: Path) -> None:
        """Read-only .gitignore causes migration to fail with a clear error message."""
        # Arrange
        gitignore = migration_project / ".gitignore"
        gitignore.write_text("kitty-specs\n", encoding="utf-8")
        gitignore.chmod(0o444)
        # Assumption check
        assert not gitignore.stat().st_mode & 0o200  # not writable
        # Act / Assert
        try:
            migration = RemoveKittySpecsFromGitignoreMigration()
            result = migration.apply(migration_project)
            assert not result.success
            assert any("Failed to write .gitignore" in err for err in result.errors)
        finally:
            gitignore.chmod(0o644)


class TestMigrationRegistryCompleteness:
    """Verify all migration files are properly discoverable and registered.

    CRITICAL: This test prevents the 0.13.2 release blocker class where
    migrations existed but never reached the runtime registry.
    """

    pytestmark = [pytest.mark.adversarial, pytest.mark.fast]

    def test_all_migration_files_are_registered(self) -> None:
        """Verify every m_*.py file in migrations/ is discovered and registered.

        This prevents silent bugs where migrations exist but never run during
        `spec-kitty upgrade` because discovery/import wiring skipped them.

        Bug prevented: 0.13.2 release blocker (4 migrations missing from registry)
        """
        # Arrange
        migration_files = sorted([f.stem for f in MIGRATIONS_DIR.glob("m_*.py") if f.stem != "__init__"])
        # Assumption check
        assert len(migration_files) > 0, "No migration files found"
        # Act
        MigrationRegistry.clear()
        auto_discover_migrations()
        registered_migrations = MigrationRegistry.get_all()
        # Assert
        assert len(migration_files) == len(registered_migrations), (
            f"Migration registry incomplete!\n"
            f"Found {len(migration_files)} migration files in {MIGRATIONS_DIR}\n"
            f"but only {len(registered_migrations)} are registered.\n\n"
            f"Migration files ({len(migration_files)}):\n"
            + "\n".join(f"  - {f}" for f in migration_files)
            + f"\n\nRegistered migrations ({len(registered_migrations)}):\n"
            + "\n".join(f"  - {m.migration_id}" for m in registered_migrations)
            + "\n\nLikely cause: Missing imports in "
            "src/specify_cli/upgrade/migrations/__init__.py auto-discovery\n"
            "or a migration module missing @MigrationRegistry.register"
        )


# TODO(conventions): retrofit remaining test bodies
