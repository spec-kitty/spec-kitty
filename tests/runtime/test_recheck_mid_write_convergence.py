"""#4174 landing-pass Concern 1: ``recheck_assets`` must wait on the anchor
lock instead of crashing on a mid-write unlocked sample.

Companion to ``tests/runtime/test_ensure_runtime_concurrency.py`` (WP01/WP03,
#4017) and ``tests/runtime/test_generic_asset_scope.py`` (WP04). Those
modules drive the loser/winner interleave where the winner has ALREADY
FULLY materialized the shared home by the time the loser re-observes it --
WP02's role-tagged content tolerance alone converges that case without ever
needing this module's fix, because the unlocked ``check_assets`` sample
already finds byte-identical canonical content.

This module drives a DIFFERENT, narrower window a second-opinion review
squad found still open after #4017 landed: a peer that has materialized
only the STAGE-0 directory-create writes from ``_write_order`` (every
directory this batch will create exists) but has not yet written any
content file. ``AssetPreparation.finish()``'s own write ordering guarantees
production code always reaches this exact intermediate state on a genuine
concurrent cold install (all directories precede all content, unconditionally,
system-wide) -- this is not a synthetic corner case.

Pre-fix, ``recheck_assets`` computed one UNLOCKED ``check_assets(assessment)``
sample and, whenever it found ANY diagnostics on an owner that had effects
and a ``PreparedAssets`` payload, returned those diagnostics immediately --
never attempting the anchor flock at all. A directory-only mid-write sample
trips exactly this: the directory observation is content-kind-tolerant on
its own, but that tolerance additionally demands EVERY genuine content file
in the batch already match canonical bytes on disk (see ``check_assets``'s
``content_confirmed`` computation) -- and mid-write, none of them do yet --
so the unlocked sample raises ``Global asset input changed`` and the caller
(``bootstrap.ensure_runtime`` et al.) turns that into an uncaught
``RuntimeError`` with no try/except at the CLI boundary (``specify_cli/
__init__.py``).

The fix: when the assessment has effects and a ``PreparedAssets`` payload,
``recheck_assets`` must proceed to acquire the lock regardless of what the
unlocked sample found, and treat only the UNDER-LOCK ``check_assets`` result
as authoritative -- by the time the anchor flock is actually granted, a
genuine concurrent peer holding it while writing will have finished, and the
home will be fully materialized.

The interleave is forced deterministically (never a flaky sleep/repeat): the
directory-only mid-write state is manufactured directly from the SAME stale,
real cold-home assessment the test then feeds back into ``ensure_runtime()``,
and the "peer finishes while we wait for the lock" event is injected at the
exact point production code attempts to acquire that lock -- WP04
(cross-os-primitive-unification) migrated that acquisition off the retired
``bootstrap._lock_exclusive`` onto ``kernel.locks.machine_file_lock``, so the
injection now uses that primitive's own G6 test-double seam
(``kernel.locks.SyncMachineFileLock``, looked up through the module's own
namespace at call time): a subclass whose ``__enter__`` materializes the
remaining content for real (via the module's own ``_write_asset``) before
delegating to the real acquire.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import specify_cli.runtime.asset_preparation as asset_preparation
import specify_cli.runtime.bootstrap as bootstrap
from specify_cli.runtime.asset_preparation import PreparedAssets
from specify_cli.runtime.bootstrap import assess_runtime, ensure_runtime

pytestmark = [pytest.mark.unit, pytest.mark.fast]

GLOBAL_ASSET_INPUT_CHANGED_SIGNAL = "Global asset input changed"
CONCURRENT_PEER_NO_OP_SIGNAL = "already materialized by a concurrent peer; nothing applied"


@pytest.fixture()
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ``SPEC_KITTY_HOME`` at a genuinely cold (nonexistent) directory."""
    home = tmp_path / "kittify"
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
    return home


@pytest.fixture()
def fake_assets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a minimal fake package asset root and point discovery at it.

    Mirrors ``tests/runtime/test_ensure_runtime_concurrency.py``'s fixture of
    the same name so ``assess_runtime()``/``ensure_runtime()`` can run for
    real without a full installed package layout.
    """
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


class TestRecheckAssetsDirectoriesOnlyMidWriteInterleave:
    """A loser sampling a shared home mid-write (dirs present, content
    absent) must wait on the anchor lock, not crash on the unlocked sample.
    """

    def test_loser_survives_directories_only_mid_write_peer(
        self,
        fake_home: Path,
        fake_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        assert not fake_home.exists(), "fixture must start genuinely cold"
        real_assess_runtime = bootstrap.assess_runtime

        # --- Arrange: capture a real, cold create-plan. ---
        stale_assessment = assess_runtime()
        assert stale_assessment.complete and stale_assessment.effects
        prepared = stale_assessment.prepared
        assert isinstance(prepared, PreparedAssets)

        dir_writes = [w for w in prepared.writes if w.effect.after.kind == "directory"]
        content_writes = [w for w in prepared.writes if w.effect.after.kind == "file"]
        assert dir_writes, "fixture must produce at least one directory create to model the mid-write window"
        assert content_writes, "fixture must produce at least one content-file create to model the mid-write window"

        # --- Simulate a peer that completed ONLY _write_order's stage-0 ---
        # directory creates -- every directory this batch will create now
        # exists, but no content file has landed yet.
        for write in dir_writes:
            write.effect.destination.mkdir(mode=write.effect.after.mode or 0o755, parents=True, exist_ok=True)
        assert all(not w.effect.destination.exists() for w in content_writes), "content must still be genuinely absent at the mid-write sample point"

        # --- The loser's own ensure_runtime() call observes this EXACT ---
        # stale, pre-mid-write assessment on its first assess -- exactly
        # what an independent concurrent process would have captured before
        # the peer above started writing.
        calls = {"assess": 0}

        def _fake_assess_runtime(**kwargs: object) -> object:
            calls["assess"] += 1
            if calls["assess"] == 1:
                return stale_assessment
            return real_assess_runtime(**kwargs)

        monkeypatch.setattr(bootstrap, "assess_runtime", _fake_assess_runtime)

        # --- Inject "the peer finishes while we wait for the lock" at the ---
        # exact point production code attempts to acquire the (now
        # canonical) lock -- via kernel.locks' own G6 test-double seam.
        import kernel.locks as kernel_locks

        real_lock_cls = kernel_locks.SyncMachineFileLock
        lock_calls = {"n": 0}

        class _CompletingLock(real_lock_cls):  # type: ignore[misc]
            def __enter__(self) -> object:
                lock_calls["n"] += 1
                if lock_calls["n"] == 1:
                    for write in prepared.writes:
                        if write.effect.after.kind != "directory":
                            asset_preparation._write_asset(write)
                return super().__enter__()

        monkeypatch.setattr(kernel_locks, "SyncMachineFileLock", _CompletingLock)

        with caplog.at_level("INFO", logger=bootstrap.logger.name):
            ensure_runtime()  # must NOT raise -- the loser converges to a no-op.

        assert lock_calls["n"] >= 1, "the fix must reach lock acquisition instead of short-circuiting on the unlocked mid-write sample"
        assert calls["assess"] >= 2, "the fix must re-assess under the held lock, not just once up front"
        joined = "\n".join(caplog.messages)
        assert GLOBAL_ASSET_INPUT_CHANGED_SIGNAL not in joined
        assert CONCURRENT_PEER_NO_OP_SIGNAL in joined, f"expected the OPERATOR_SIGNAL_CONTRACT sentence on the converged-no-op path, got: {caplog.messages!r}"
