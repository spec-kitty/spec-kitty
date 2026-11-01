"""#6719 — activation writes run under the run-wide charter synthesis lock.

Two writers raced a synthesis run without the lock (#6453 owns it):

1. ``charter activate`` / ``deactivate`` read-modify-write the activation config unlocked, so a deactivation
   that lands inside a synthesis run's append window is lost — the run's stale document overwrites it, or the
   deactivation refuses with ``precondition_changed`` and the artifact stays in force.
2. The activation-ledger migration's manifest stamp (``activation_ledger._stamp_manifest``) reads and rewrites
   the whole synthesis manifest unlocked, so it can drop entries a concurrent run just wrote.

The two two-writer tests below are the issue's acceptance criteria; the refusal tests pin the behaviour when a
synthesis run already holds the lock (bounded wait, coded refusal, nothing written). The handshake is the one
#6453 introduced: pause the first writer at its write and release it only once the second is *provably* waiting
on the lock, so the test never depends on a sleep.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

import charter.activation.synthesizer.synthesis_lock as lock_module
from charter.activation.activation_ledger import apply_ledger_migration, plan_ledger_migration
from charter.activation.invocation_context import ProjectContext
from charter.activation.pack_manager import ActiveCharterManager
from charter.activation.synthesizer.manifest import (
    MANIFEST_PATH,
    ManifestArtifactEntry,
    finalize_manifest,
    load_yaml,
)
from charter.activation.synthesizer.reach_only import append_synthesized_activations
from charter.activation.synthesizer.synthesis_lock import SynthesisLockHeldError, synthesis_lock
from charter.bundle import compute_bundle_content_hash
from specify_cli.cli.commands.charter import charter_app
from tests._factories.activation_ledger import read_activation_ledger, seed_activation_ledger
from tests.charter.test_activate_restamps_bundle_hash import _project

pytestmark = pytest.mark.integration

runner = CliRunner()

_DIRECTIVE = "001-architectural-integrity-standard"
_OTHER_DIRECTIVE = "010-specification-fidelity-requirement"
_TACTIC = "existing-tactic"
_NEW_TACTIC = "synthesis-created-tactic"
_CONCURRENT_SLUG = "concurrent-synthesis-tactic"

#: Hard join timeout: a hang must fail the test, never block CI.
_JOIN_S = 30.0
#: How long a paused writer waits for proof that the peer is blocked on the lock.
_CONTENTION_WAIT_S = 5.0


def _project_with_ledger(tmp_path: Path) -> Path:
    """Migrated-shape project: activation lives in the ledger, no legacy activation keys beside it."""
    repo = _project(tmp_path)
    charter_yaml = repo / ".kittify" / "charter" / "charter.yaml"
    document = yaml.safe_load(charter_yaml.read_text(encoding="utf-8")) or {}
    document.pop("activated_directives", None)
    charter_yaml.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    seed_activation_ledger(repo, activated_directives=[_DIRECTIVE], activated_tactics=[_TACTIC])
    return repo


def _run_concurrently(first: Callable[[], Any], second: Callable[[], Any]) -> list[BaseException]:
    errors: list[BaseException] = []

    def _guard(job: Callable[[], Any]) -> Callable[[], None]:
        def _run() -> None:
            try:
                job()
            except BaseException as exc:  # noqa: BLE001 — surface every writer failure to the assertion
                errors.append(exc)

        return _run

    threads = [threading.Thread(target=_guard(first)), threading.Thread(target=_guard(second))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=_JOIN_S)
        assert not thread.is_alive(), "a writer hung"
    return errors


class _FirstWriterPauses:
    """Pause writer A at *pause_at* until writer B is provably blocked on the synthesis lock.

    Writer A is the writer under test (the one that must hold the lock): it pauses at its write; B fails a
    non-blocking lock attempt only while A holds the lock. Without the lock B never blocks, A times out and the
    interleaving that loses a write happens — which is exactly what the assertions catch.

    ``when="after"`` pauses after the seam returned (used when the seam IS the read: the pause must sit between
    the read and the write to open the lost-update window at all). ``started`` lets the peer thread wait until
    writer A is inside its write path, so the thread schedule never decides which writer goes first.
    """

    def __init__(self, monkeypatch: pytest.MonkeyPatch, pause_at: tuple[Any, str], *, when: str = "before") -> None:
        from kernel.locks import _LockCore

        assert when in {"before", "after"}
        self.contended = threading.Event()
        self.started = threading.Event()
        self.timed_out = False
        self._first = threading.Lock()
        real = getattr(pause_at[0], pause_at[1])
        real_try = _LockCore.try_lock_once

        def _pause() -> None:
            self.started.set()
            if self._first.acquire(blocking=False):  # only the first (paused) writer waits
                self.timed_out = not self.contended.wait(timeout=_CONTENTION_WAIT_S)

        def _pausing(*args: Any, **kwargs: Any) -> Any:
            if when == "before":
                _pause()
                return real(*args, **kwargs)
            result = real(*args, **kwargs)
            _pause()
            return result

        def _try(core: Any, fd: int) -> bool:
            acquired = real_try(core, fd)
            if not acquired:
                self.contended.set()
            return acquired

        monkeypatch.setattr(pause_at[0], pause_at[1], _pausing)
        monkeypatch.setattr(_LockCore, "try_lock_once", _try)

    def assert_lock_was_contended(self) -> None:
        assert self.contended.is_set(), "the peer never waited on the synthesis lock; the race was not exercised"
        assert not self.timed_out


@contextmanager
def hold_from_other_thread(repo_root: Path) -> Iterator[None]:
    """Hold the synthesis lock on another thread; same-thread re-entry would prove nothing."""
    acquired = threading.Event()
    release = threading.Event()

    def _holder() -> None:
        with synthesis_lock(repo_root):
            acquired.set()
            release.wait(timeout=_JOIN_S)

    thread = threading.Thread(target=_holder, daemon=True)
    thread.start()
    assert acquired.wait(timeout=10), "the holder thread never acquired the lock"
    try:
        yield
    finally:
        release.set()
        thread.join(timeout=10)


# ---------------------------------------------------------------------------
# US1 / FR-001: a deactivation is never undone by a synthesis append
# ---------------------------------------------------------------------------


def test_deactivate_racing_a_synthesis_append_keeps_both_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A deactivate and a synthesis append that interleave must both survive (#6719, AC-1)."""
    from charter.activation import pack_manager

    repo = _project_with_ledger(tmp_path)
    handshake = _FirstWriterPauses(monkeypatch, (pack_manager, "commit_plan"))

    def _deactivate() -> None:
        ActiveCharterManager().deactivate(ProjectContext(repo_root=repo), kind="directive", artifact_id=_DIRECTIVE)

    def _synthesis() -> None:
        assert handshake.started.wait(timeout=_CONTENTION_WAIT_S), "the deactivate never reached its write path"
        append_synthesized_activations(repo, {"tactic": [_NEW_TACTIC]})

    errors = _run_concurrently(_deactivate, _synthesis)

    assert not errors, f"a writer failed: {errors}"
    handshake.assert_lock_was_contended()
    ledger = read_activation_ledger(repo)
    # The operator's deactivation stuck ...
    assert ledger.get("deactivated_directives") == [_DIRECTIVE]
    assert _DIRECTIVE not in (ledger.get("activated_directives") or [])
    # ... and the positive control: synthesis's append survived beside it.
    assert _NEW_TACTIC in (ledger.get("activated_tactics") or [])
    assert _TACTIC in (ledger.get("activated_tactics") or [])


# ---------------------------------------------------------------------------
# US2 / FR-004: the migration's manifest stamp keeps concurrent synthesis entries
# ---------------------------------------------------------------------------


def _synthesis_manifest_write(repo: Path, slug: str) -> None:
    """One synthesis run's manifest write, under the run-wide lock as ``charter synthesize`` holds it."""
    with synthesis_lock(repo):
        manifest = load_yaml(repo / MANIFEST_PATH)
        entry = ManifestArtifactEntry(
            kind="tactic",
            slug=slug,
            path=f".kittify/charter-packs/tactics/{slug}.yaml",
            provenance_path=f".kittify/charter/provenance/{slug}.yaml",
            content_hash="0" * 64,
        )
        updated = manifest.model_copy(update={"artifacts": [*manifest.artifacts, entry], "bundle_content_hash": compute_bundle_content_hash(repo)})
        from charter.activation.synthesizer.synthesize_pipeline import canonical_yaml

        (repo / MANIFEST_PATH).write_text(canonical_yaml(finalize_manifest(updated).model_dump(mode="python")).decode("utf-8"), encoding="utf-8")


def test_migration_manifest_stamp_keeps_a_concurrent_synthesis_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The migration's stamp must not drop a manifest entry a synthesis run wrote concurrently (#6719, AC-2)."""
    from charter.activation import activation_ledger

    repo = _project(tmp_path)  # legacy activation key beside no ledger: the migration has work to do
    plan = plan_ledger_migration(repo)
    assert plan.ledger_values, "fixture has no legacy keys to migrate"
    # The pause must sit between the stamp's read and its write, so this one pauses *after* the seam.
    handshake = _FirstWriterPauses(monkeypatch, (activation_ledger, "_stampable_manifest"), when="after")

    def _synthesis() -> None:
        assert handshake.started.wait(timeout=_CONTENTION_WAIT_S), "the migration never read the manifest"
        _synthesis_manifest_write(repo, _CONCURRENT_SLUG)

    errors = _run_concurrently(lambda: apply_ledger_migration(repo, plan), _synthesis)

    assert not errors, f"a writer failed: {errors}"
    handshake.assert_lock_was_contended()
    manifest = load_yaml(repo / MANIFEST_PATH)
    # The positive control: the concurrently written entry is still registered ...
    assert _CONCURRENT_SLUG in {entry.slug for entry in manifest.artifacts}
    # ... and the migration still landed (the legacy key moved to the ledger).
    assert plan.strips, "fixture has no legacy surface to strip"


# ---------------------------------------------------------------------------
# FR-005: a held lock is a coded refusal with nothing written
# ---------------------------------------------------------------------------


def _snapshot(repo: Path) -> dict[str, bytes]:
    """Every project file, minus the synthesis lock files themselves (their creation is the holder's)."""
    return {
        path.relative_to(repo).as_posix(): path.read_bytes() for path in sorted(repo.rglob("*")) if path.is_file() and "spec-kitty-locks" not in path.as_posix()
    }


def test_activate_and_deactivate_refuse_while_a_synthesis_run_holds_the_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``charter activate``/``deactivate`` wait, then refuse, and write nothing (#6719, FR-005)."""
    monkeypatch.setattr(lock_module, "_SYNTHESIS_LOCK_TIMEOUT_S", 0.2)
    repo = _project_with_ledger(tmp_path)
    before = _snapshot(repo)

    with hold_from_other_thread(repo):
        activate = runner.invoke(charter_app, ["activate", "directive", _OTHER_DIRECTIVE, "--repo-root", str(repo)])
        deactivate = runner.invoke(charter_app, ["deactivate", "directive", _DIRECTIVE, "--repo-root", str(repo)])

    for result in (activate, deactivate):
        assert result.exit_code == 1, result.output
        assert "CHARTER_SYNTHESIS_LOCK_HELD" in result.output
    assert _snapshot(repo) == before, "a refused command wrote to the project"


def test_activate_json_refusal_carries_the_lock_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The ``--json`` form emits the same code in the canonical error envelope (#6719, FR-005)."""
    monkeypatch.setattr(lock_module, "_SYNTHESIS_LOCK_TIMEOUT_S", 0.2)
    repo = _project_with_ledger(tmp_path)

    with hold_from_other_thread(repo):
        result = runner.invoke(charter_app, ["activate", "directive", _OTHER_DIRECTIVE, "--json", "--repo-root", str(repo)])

    assert result.exit_code == 1, result.output
    payload = yaml.safe_load(result.stdout)
    assert payload["error"]["code"] == "CHARTER_SYNTHESIS_LOCK_HELD"


def test_preset_apply_refuses_while_a_synthesis_run_holds_the_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``charter activate --preset`` plans and applies under the same window (#6719, FR-002)."""
    monkeypatch.setattr(lock_module, "_SYNTHESIS_LOCK_TIMEOUT_S", 0.2)
    repo = _project_with_ledger(tmp_path)
    before = _snapshot(repo)

    with hold_from_other_thread(repo):
        result = runner.invoke(charter_app, ["activate", "--pack", "built-in", "--preset", "default", "--force", "--repo-root", str(repo)])

    assert result.exit_code == 1, result.output
    assert "CHARTER_SYNTHESIS_LOCK_HELD" in result.output
    assert _snapshot(repo) == before


def test_migration_refuses_while_a_synthesis_run_holds_the_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The migration's ledger-write/stamp/strip unit refuses rather than writing unlocked (#6719, FR-004/FR-005)."""
    monkeypatch.setattr(lock_module, "_SYNTHESIS_LOCK_TIMEOUT_S", 0.2)
    repo = _project(tmp_path)
    plan = plan_ledger_migration(repo)
    before = _snapshot(repo)

    with hold_from_other_thread(repo), pytest.raises(SynthesisLockHeldError):
        apply_ledger_migration(repo, plan)

    assert _snapshot(repo) == before, "a refused migration wrote to the project"


def test_unavailable_lock_maps_to_its_coded_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Git that cannot be invoked refuses the write instead of placing an unlocked no-op (#6719, FR-005)."""
    import charter.activation.synthesizer.synthesis_lock as module

    from kernel.errors import KittyInternalConsistencyError
    from kernel.git_topology import GitTopologyUnavailableError

    repo = _project_with_ledger(tmp_path)
    before = _snapshot(repo)

    def _unavailable(root: Path) -> Path:
        raise GitTopologyUnavailableError(root, "git is not runnable")

    monkeypatch.setattr(module, "git_common_dir", _unavailable)

    with pytest.raises(KittyInternalConsistencyError) as refused:
        ActiveCharterManager().deactivate(ProjectContext(repo_root=repo), kind="directive", artifact_id=_DIRECTIVE)

    assert refused.value.code == "CHARTER_SYNTHESIS_LOCK_UNAVAILABLE"
    assert _snapshot(repo) == before
