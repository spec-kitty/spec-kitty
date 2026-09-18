"""Regression (#4703): 4.0.0rc3 is unusable on Windows — every command aborts
with ``[Errno 13] Permission denied`` because the runtime bootstrap reads its
own held lock file.

On Windows ``msvcrt.locking()`` is *mandatory*: while ``recheck_assets`` holds an
exclusive lock on the owner lock file (``cache/.update.lock``), the under-lock
``check_assets`` recheck re-reads every observed path via ``node_state`` ->
``read_bytes`` — including the lock file itself — and the OS refuses that read
even to the locking process, surfacing as ``PermissionError`` errno 13. On POSIX
``flock`` is advisory so the read succeeds, which is why CI never caught it.

These tests simulate the Windows mandatory-lock semantics on POSIX by making
``node_state`` raise ``PermissionError`` when asked to read a path that is
currently in ``_HELD_LOCKS`` — a faithful reproduction through the real
``ensure_runtime()`` entry point. The regression must be RED on the pre-fix code
(``check_assets`` reads the lock under the hold) and GREEN once the lock node is
excluded from its own verification read set.

Introduced by the #4017 re-assess-under-lock landing (the under-lock
``check_assets`` call); 3.2.7 predates it and works.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import specify_cli.runtime.asset_preparation as ap
import specify_cli.runtime.bootstrap as bootstrap
from specify_cli.runtime.bootstrap import assess_runtime, ensure_runtime

pytestmark = [pytest.mark.unit, pytest.mark.fast]

FAKE_VERSION = "99.0.0-test"
GLOBAL_ASSET_INPUT_CHANGED_SIGNAL = "Global asset input changed"


@pytest.fixture()
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ``SPEC_KITTY_HOME`` at a temp dir (cold on first use)."""
    home = tmp_path / "kittify"
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
    return home


@pytest.fixture()
def fake_assets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Minimal fake package asset root; mirrors ``test_bootstrap_unit``."""
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


def _warm_home_with_pending_effects(fake_home: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Materialize a warm home, then re-arm a pending effect while KEEPING the
    persistent owner lock on disk — the exact precondition the crash needs.

    The crash is warm-path only: ``recheck_assets`` acquires the owner lock (and
    the under-lock recheck reads it) ONLY when the lock file already exists AND
    the assessment still carries effects. A cold or fully-converged home takes no
    lock and would pass vacuously.
    """
    monkeypatch.setattr(bootstrap, "_get_cli_version", lambda: FAKE_VERSION)
    ensure_runtime()  # cold: materializes home, creates cache/.update.lock + version.lock

    lock_path = fake_home / "cache" / ".update.lock"
    assert lock_path.exists(), "cold bootstrap must create the persistent owner lock"

    # Re-arm a pending effect without removing the lock: a missing version stamp
    # forces the slow path (a genuine re-apply), so the next assessment has
    # effects and recheck_assets will acquire + read the still-present lock.
    (fake_home / "cache" / "version.lock").unlink()

    reassessment = assess_runtime()
    assert reassessment.effects, "setup guard: the re-armed assessment must carry effects"
    prepared = reassessment.prepared
    observed = {observation.path for observation in prepared.observations}
    assert set(prepared.lock_paths) <= observed, "setup guard: the owner lock must be observed"
    assert lock_path in set(prepared.lock_paths), "setup guard: .update.lock must be an owner lock path"
    return lock_path


def _mandatory_lock_read_simulation(lock_paths_seen: list[Path] | None = None):
    """A ``node_state`` replacement that mimics Windows mandatory-lock reads: a
    *content read* (``read_content=True``) of a path currently held in
    ``_HELD_LOCKS`` raises ``PermissionError`` errno 13 (``filename=None`` and
    ``winerror=None``, byte for byte the observed Windows signature). An
    ``lstat``-only observation (``read_content=False``) does NOT fail — on
    Windows only opening/reading the locked bytes is refused, not stat'ing them.
    Every other read is real.
    """
    real_node_state = ap.node_state

    def fake_node_state(path: Path, *, read_content: bool = True) -> object:
        if read_content and path in ap._HELD_LOCKS.get():
            if lock_paths_seen is not None:
                lock_paths_seen.append(path)
            raise PermissionError(13, "Permission denied")
        return real_node_state(path, read_content=read_content)

    return fake_node_state


class TestSelfHeldLockRead:
    """FR-001 / NFR-001 — the under-lock recheck must not read its own lock."""

    def test_ensure_runtime_survives_reading_its_own_held_lock(
        self,
        fake_home: Path,
        fake_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AC-1: with the owner lock held and its read failing (Windows
        mandatory-lock semantics), ``ensure_runtime()`` must NOT raise. RED on
        pre-fix code (``check_assets`` reads ``.update.lock`` under the hold).
        """
        _warm_home_with_pending_effects(fake_home, monkeypatch)
        monkeypatch.setattr(ap, "node_state", _mandatory_lock_read_simulation())

        # Must complete: the lock node is excluded from its own verification read.
        ensure_runtime()

    def test_owner_lock_is_never_read_while_held(
        self,
        fake_home: Path,
        fake_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AC-2 (anti-false-green): the owner lock stays OBSERVED, but its bytes
        are never read while the lock is held. Guards against a wrong 'fix' that
        simply drops the lock from ``observations`` (which would pass AC-1 for
        the wrong reason and weaken future guarantees).
        """
        lock_path = _warm_home_with_pending_effects(fake_home, monkeypatch)
        seen: list[Path] = []
        monkeypatch.setattr(ap, "node_state", _mandatory_lock_read_simulation(seen))

        ensure_runtime()

        assert lock_path not in seen, "the held owner lock must never be read during recheck"


class TestSourceDriftStillCaught:
    """NFR-001 — the fix must not over-suppress genuine drift detection."""

    def test_genuine_source_drift_still_raises_under_lock_sim(
        self,
        fake_home: Path,
        fake_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AC-1 cross-check: excluding the lock node must NOT swallow a real
        package-source change. With the mandatory-lock sim active, a mutated
        template source must still raise the organic #4017 signal.
        """
        _warm_home_with_pending_effects(fake_home, monkeypatch)

        # Capture a stale assessment, THEN mutate a package source — the same
        # assess→mutate→apply drift shape as test_reassess_under_lock's T009, so
        # the under-lock recheck genuinely observes source drift.
        stale = assess_runtime()
        assert stale.complete and stale.effects
        template = fake_assets / "software-dev" / "templates" / "spec.md"
        template.write_text("mutated package source after assessment")
        monkeypatch.setattr(bootstrap, "assess_runtime", lambda **_: stale)
        monkeypatch.setattr(ap, "node_state", _mandatory_lock_read_simulation())

        with pytest.raises(RuntimeError) as exc_info:
            ensure_runtime()
        assert GLOBAL_ASSET_INPUT_CHANGED_SIGNAL in str(exc_info.value)


class TestReadFailureDiagnosticNamesPath:
    """FR-002 — a swallowed read failure must name the failing path."""

    def test_diagnostic_includes_failing_path_when_a_managed_asset_read_fails(
        self,
        fake_home: Path,
        fake_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AC-3: a ``PermissionError`` on a managed (non-lock) asset — the
        Windows signature with ``filename=None`` — must surface a
        ``precondition_changed`` diagnostic naming the path, not a bare
        ``[Errno 13] Permission denied``. Exercised directly at the
        ``check_assets`` seam where the diagnostic is minted.
        """
        _warm_home_with_pending_effects(fake_home, monkeypatch)
        assessment = assess_runtime()
        prepared = assessment.prepared
        lock_paths = set(prepared.lock_paths)
        target = next(o.path for o in prepared.observations if o.state.kind == "file" and o.path not in lock_paths)

        real_node_state = ap.node_state

        def fake_node_state(path: Path, *, read_content: bool = True) -> object:
            if read_content and path == target:
                raise PermissionError(13, "Permission denied")  # filename=None, like Windows
            return real_node_state(path, read_content=read_content)

        monkeypatch.setattr(ap, "node_state", fake_node_state)

        diagnostics = ap.check_assets(assessment)
        assert diagnostics, "a read failure must produce a precondition_changed diagnostic"
        assert str(target) in diagnostics[0].message, f"diagnostic must name the failing path, got: {diagnostics[0].message!r}"
