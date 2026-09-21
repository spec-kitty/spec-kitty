"""WP04 migration coverage: asset_preparation's owner-lock coordination on
``kernel.locks`` (cross-os-primitive-unification, #4714).

Scope: this file proves the MIGRATION -- that ``recheck_assets``/
``_apply_retained_assets`` now route through ``kernel.locks.machine_file_lock``
instead of a raw ``msvcrt``/``fcntl`` call, that the cold-install path
serializes on ONE uniform sentinel file regardless of platform (the
POSIX-directory-flock shape is retired -- kernel.locks cannot lock a
directory fd), and that the #4703 read-safety invariant (never read a
payload under a held lock) is preserved end to end through the migrated
primitive. It does not re-prove kernel.locks' own cross-platform parity --
that is ``tests/kernel/test_locks.py``'s job (WP03).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

import specify_cli.runtime.asset_preparation as ap
import specify_cli.runtime.bootstrap as bootstrap
from specify_cli.runtime.bootstrap import assess_runtime, ensure_runtime
from specify_cli.tool_surface.operations import (
    ApplyConsent,
    FileState,
    OperationRoot,
    OwnerAssessment,
    OwnershipProof,
    PhysicalEffect,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

FAKE_VERSION = "99.0.0-test"


@pytest.fixture()
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "kittify"
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
    return home


@pytest.fixture()
def fake_assets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pkg_root = tmp_path / "package"
    missions = pkg_root / "missions"
    (missions / "software-dev").mkdir(parents=True)
    (missions / "software-dev" / "mission.yaml").write_text("test-mission")
    (missions / "software-dev" / "templates").mkdir()
    (missions / "software-dev" / "templates" / "spec.md").write_text("test-template")
    scripts = pkg_root / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "validate.py").write_text("# validate")
    (pkg_root / "AGENTS.md").write_text("# Agents")
    monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(missions))
    return missions


class TestNoRawLockPrimitive:
    """FR-010: no raw msvcrt/fcntl remains; the module routes through
    kernel.locks exclusively."""

    def test_module_imports_the_canonical_primitive(self) -> None:
        assert ap.machine_file_lock is not None

    def test_module_has_no_bootstrap_lock_exclusive_reference(self) -> None:
        """The pre-migration ``bootstrap._lock_exclusive`` import is gone --
        confirms this module no longer round-trips through bootstrap for its
        own OS-level locking."""
        assert not hasattr(bootstrap, "_lock_exclusive")


class TestColdInstallUsesOneUniformSentinel:
    """WP04 reconciliation: the POSIX anchor-directory-flock shape is
    retired. A cold install serializes on the SAME dedicated sentinel file
    on every platform -- kernel.locks cannot lock a directory fd (G1: a
    dedicated regular lock-only path only), so unifying onto the sentinel
    is the only shape that lets recheck_assets fully retire raw msvcrt/fcntl
    while still serializing cold installers of the same anchor.
    """

    def test_cold_install_locks_the_sentinel_and_never_the_anchor_directory(
        self,
        fake_home: Path,
        fake_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(bootstrap, "_get_cli_version", lambda: FAKE_VERSION)
        assessment = assess_runtime()  # cold: effects present, lock files absent
        assert assessment.effects
        prepared = assessment.prepared
        assert all(not p.exists() for p in prepared.lock_paths), "setup guard: a cold install has no lock files yet"

        sentinel = ap._cold_install_sentinel(prepared.anchor)
        if sentinel.exists():
            sentinel.unlink()

        with ap.recheck_assets(assessment):
            assert sentinel.exists(), "a cold install must create + lock the uniform sentinel"

        # #4756 WP02: the sentinel now resolves as a SIBLING of the per-user
        # runtime state root (kernel.paths.get_runtime_state_root(), never
        # the world-shared tempfile.gettempdir()) instead of a machine-temp
        # file -- but it still stays strictly outside the managed asset
        # tree, on every platform, so it never enters asset verification
        # (and, deliberately, never nests inside fake_home -- see
        # _cold_install_sentinel's docstring for why a nested sentinel would
        # corrupt assess_runtime's own drift tracking on a cold install).
        assert "-cold-install" in sentinel.parent.name
        assert fake_home not in sentinel.parents

    def test_sentinel_key_is_stable_across_equivalent_anchor_spellings(self, tmp_path: Path) -> None:
        """FR-011: anchor normalization -- case and a trailing separator must
        key the SAME sentinel, not silently split into two unrelated locks."""
        anchor = tmp_path / "Kittify"
        anchor.mkdir()
        canonical = ap._cold_install_sentinel(anchor)
        with_trailing_slash = ap._cold_install_sentinel(Path(str(anchor) + "/"))
        assert canonical == with_trailing_slash


class TestRecheckLocksExistingOwnerLockViaCanonicalPrimitive:
    """FR-B/#4703 (carried over from the pre-migration primitive): the
    existing owner lock is acquired for real, and the process never reads
    its own held lock's payload."""

    def test_warm_recheck_survives_reading_its_own_held_lock(
        self,
        fake_home: Path,
        fake_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(bootstrap, "_get_cli_version", lambda: FAKE_VERSION)
        ensure_runtime()  # cold materialize: creates cache/.update.lock + version.lock

        lock_path = fake_home / "cache" / ".update.lock"
        assert lock_path.exists(), "cold bootstrap must create the persistent owner lock"

        # Re-arm a pending effect without removing the lock, so the next
        # recheck genuinely acquires + observes the still-present lock.
        (fake_home / "cache" / "version.lock").unlink()
        reassessment = assess_runtime()
        assert reassessment.effects
        prepared = reassessment.prepared
        assert lock_path in set(prepared.lock_paths)

        real_node_state = ap.node_state
        seen_content_reads: list[Path] = []

        def guarded_node_state(path: Path, *, read_content: bool = True) -> object:
            if read_content and path in ap._HELD_LOCKS.get():
                seen_content_reads.append(path)
                raise PermissionError(13, "Permission denied")
            return real_node_state(path, read_content=read_content)

        monkeypatch.setattr(ap, "node_state", guarded_node_state)

        with ap.recheck_assets(reassessment):
            pass  # must not raise despite the simulated mandatory-lock read failure

        assert lock_path not in seen_content_reads, "the held owner lock must never be content-read"

    def test_apply_creates_and_locks_the_persistent_owner_lock(
        self,
        fake_home: Path,
        fake_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The first cold apply must materialize the persistent owner lock
        through the canonical primitive (not a raw exclusive-create+flock)."""
        monkeypatch.setattr(bootstrap, "_get_cli_version", lambda: FAKE_VERSION)
        ensure_runtime()

        lock_path = fake_home / "cache" / ".update.lock"
        assert lock_path.is_file()
        # kernel.locks always opens 0o600; _apply_retained_assets re-chmods
        # to the assessed mode (0o644) immediately after acquiring.
        assert (lock_path.stat().st_mode & 0o777) == 0o644


class TestOwnerLockAcquireNeverNarrowsSharedCacheDirMode:
    """Regression for the #4714 WP04 review rejection (Finding #1): the
    owner lock's parent (the managed cache dir) is a SHARED directory this
    module tracks at 0o755 alongside the inventory JSON and version stamp
    -- ``kernel.locks._ensure_dir`` must never narrow it to 0o700 on
    acquire, because it did not create it. Pre-fix, every acquire silently
    chmod'd the shared dir; the caller-side workaround
    (``_restore_owner_lock_parent_mode``) that used to paper over this at
    the call site is gone -- the primitive itself must never make the
    write in the first place."""

    def test_cache_dir_mode_unchanged_after_owner_lock_acquire_and_release(
        self,
        fake_home: Path,
        fake_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(bootstrap, "_get_cli_version", lambda: FAKE_VERSION)
        ensure_runtime()  # cold materialize: creates cache/ (0o755) + .update.lock + version.lock

        cache_dir = fake_home / "cache"
        lock_path = cache_dir / ".update.lock"
        assert lock_path.exists(), "cold bootstrap must create the persistent owner lock"
        assert (cache_dir.stat().st_mode & 0o777) == 0o755, "setup guard: cache dir starts shared at 0o755"

        # Re-arm a pending effect without removing the lock, so the next
        # recheck genuinely acquires the still-present owner lock.
        (cache_dir / "version.lock").unlink()
        reassessment = assess_runtime()
        assert reassessment.effects
        prepared = reassessment.prepared
        assert lock_path in set(prepared.lock_paths)

        with ap.recheck_assets(reassessment):
            assert (cache_dir.stat().st_mode & 0o777) == 0o755, "the shared cache dir must not be narrowed WHILE the owner lock is held"

        assert (cache_dir.stat().st_mode & 0o777) == 0o755, "the shared cache dir must remain 0o755 after the owner-lock acquire+release"


class TestApplyRetainedAssetsSkipsRelockOfAlreadyHeldOwnerLock:
    """A1 (#4714 WP04 review, MEDIUM advisory): a stale cold plan's own
    "create" write for the persistent owner lock must not re-acquire the
    SAME non-reentrant lock when the destination already exists at apply
    time -- the signal that ``recheck_assets`` already found it existing and
    OS-locked it for real (a racing peer materialized the lock between this
    plan's build and this apply). Re-locking would block this process
    against itself indefinitely. A genuinely cold "create" (destination
    still absent) must still lock normally."""

    def test_apply_retained_assets_does_not_relock_a_path_already_held(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        cache = tmp_path / "cache"
        cache.mkdir()
        lock_path = cache / ".update.lock"
        root = OperationRoot("runtime_bootstrap", "global", tmp_path)
        # A minimal synthetic "create the owner lock" write, standing in for
        # a stale cold plan built before a racing peer materialized the same
        # lock (the plan's own snapshot never sees that race; only
        # recheck_assets's later, under-lock check does).
        effect = PhysicalEffect(
            owner="runtime_bootstrap",
            phase="global_bootstrap",
            root=root,
            path="cache/.update.lock",
            action="create",
            before=FileState("absent"),
            after=FileState("file", sha256=ap.digest(b""), mode=0o644),
            reason="persistent-lock",
            ownership=(OwnershipProof("managed_path", "runtime_bootstrap:persistent-lock"),),
            logical_owners=("runtime_bootstrap",),
        )
        prepared = ap.PreparedAssets(
            writes=(ap.AssetWrite(effect, b""),),
            observations=(),
            environment=(),
            lock_path=lock_path,
            anchor=tmp_path,
        )
        assessment = OwnerAssessment(
            owner_key="runtime_bootstrap",
            root=root,
            effects=(effect,),
            prepared=prepared,
        )

        lock_calls: list[Path] = []
        real_lock = ap.machine_file_lock

        @contextmanager
        def spying_lock(path: Path, *, blocking: bool = True) -> Iterator[None]:
            lock_calls.append(path)
            with real_lock(path, blocking=blocking):
                yield

        monkeypatch.setattr(ap, "machine_file_lock", spying_lock)

        # Simulate recheck_assets already having found this path existing and
        # genuinely OS-locked it for real (a racing peer materialized the
        # lock) before this stale "create" plan ever reaches
        # _apply_retained_assets. machine_file_lock's O_CREAT means holding
        # this lock also materializes the file, which is exactly the signal
        # the fix keys on.
        with real_lock(lock_path, blocking=True):
            result = ap._apply_retained_assets(assessment)

        assert lock_path not in lock_calls, "must not re-acquire an already-held owner lock"
        assert result.outcome not in {"failed", "partial"}, result.diagnostics

    def test_apply_retained_assets_locks_a_genuinely_cold_create_normally(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The common (non-race) case: the destination is truly absent, so
        the guard above must NOT suppress the real lock+create."""
        cache = tmp_path / "cache"
        cache.mkdir()
        lock_path = cache / ".update.lock"
        root = OperationRoot("runtime_bootstrap", "global", tmp_path)
        effect = PhysicalEffect(
            owner="runtime_bootstrap",
            phase="global_bootstrap",
            root=root,
            path="cache/.update.lock",
            action="create",
            before=FileState("absent"),
            after=FileState("file", sha256=ap.digest(b""), mode=0o644),
            reason="persistent-lock",
            ownership=(OwnershipProof("managed_path", "runtime_bootstrap:persistent-lock"),),
            logical_owners=("runtime_bootstrap",),
        )
        prepared = ap.PreparedAssets(
            writes=(ap.AssetWrite(effect, b""),),
            observations=(),
            environment=(),
            lock_path=lock_path,
            anchor=tmp_path,
        )
        assessment = OwnerAssessment(
            owner_key="runtime_bootstrap",
            root=root,
            effects=(effect,),
            prepared=prepared,
        )
        assert not lock_path.exists(), "setup guard: genuinely cold -- the lock must not exist yet"

        lock_calls: list[Path] = []
        real_lock = ap.machine_file_lock

        @contextmanager
        def spying_lock(path: Path, *, blocking: bool = True) -> Iterator[None]:
            lock_calls.append(path)
            with real_lock(path, blocking=blocking):
                yield

        monkeypatch.setattr(ap, "machine_file_lock", spying_lock)

        result = ap._apply_retained_assets(assessment)

        assert lock_calls == [lock_path], "a genuinely cold create must still lock+create for real"
        assert lock_path.is_file()
        assert result.outcome not in {"failed", "partial"}, result.diagnostics


class TestConvergedFamilyIncludeStillNeverReadsHeldLock:
    """Regression guard for the #4703 residual fixed alongside the primitive
    migration -- unaffected by which lock primitive acquires the lock, but
    re-asserted here so a future edit to include() cannot quietly reopen it
    once ``_HELD_LOCKS`` starts tracking machine_file_lock-backed holds."""

    def test_converged_family_include_never_reads_the_held_lock(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        consent = ApplyConsent()
        cache = tmp_path / "cache"
        cache.mkdir()
        lock_path = cache / ".converged.lock"
        lock_path.write_bytes(b"")

        builder = ap.AssetPreparation(
            "converged_family",
            OperationRoot("converged_family", "global", tmp_path),
            cache,
            ".converged.lock",
            consent,
        )
        assert lock_path not in builder.observed

        reads: list[Path] = []
        real_node_state = ap.node_state

        def fake_node_state(path: Path, *, read_content: bool = True) -> object:
            if read_content and path in ap._HELD_LOCKS.get():
                reads.append(path)
                raise PermissionError(13, "Permission denied")
            return real_node_state(path, read_content=read_content)

        monkeypatch.setattr(ap, "node_state", fake_node_state)

        token = ap._HELD_LOCKS.set({lock_path})
        try:
            batch = ap._GlobalAssetPreparation(consent)
            batch.include(builder, effects=())
        finally:
            ap._HELD_LOCKS.reset(token)

        assert lock_path in batch.locks
        assert lock_path not in reads
